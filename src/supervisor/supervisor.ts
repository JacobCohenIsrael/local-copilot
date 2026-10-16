import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { POLICY, POLICY_HASH, Rejected, type Fault, type Metric, type PersistentState,
  type Proposal, type RunResult, type State, type Task, type Usage } from './contracts.js';
import { Simulator } from './simulator.js';
import { Store, type Journal } from './store.js';

const nextStates: Record<State, State[]> = {
  OFF: ['PREFLIGHT'], PREFLIGHT: ['STARTING'], STARTING: ['RUNNING'],
  RUNNING: ['STOPPING_WORKER'], STOPPING_WORKER: ['STOPPING_STRATA'],
  STOPPING_STRATA: ['COOLDOWN'], COOLDOWN: ['OFF'], FAULT: [],
};
export function inspect(store: Store): PersistentState {
  const state = store.load();
  let fault: Fault | null = null;
  if (state.policyHash !== POLICY_HASH)
    fault = { code: 'POLICY_CHANGED', atMs: 0, detail: 'Policy fingerprint changed. Human review is required; reset cannot approve policy.' };
  else if (!['OFF', 'FAULT'].includes(state.state))
    fault = { code: 'UNCLEAN_EXIT', atMs: 0, detail: 'Previous simulation did not finish. Automatic restart is blocked.' };
  if (fault && state.state !== 'FAULT') {
    state.state = 'FAULT'; state.fault = fault; state.updatedAt = new Date().toISOString();
    store.save(state); store.audit({ action: 'recovery-fault', fault });
  }
  return state;
}
export function resetFault(store: Store, reason: string, acknowledged: boolean): PersistentState {
  if (!acknowledged || reason.trim().length < 8 || reason.length > 512)
    throw new Rejected('RESET_REQUIRES_ACK', 'Simulation fault reset requires acknowledgement and an 8–512 character review reason.');
  const state = inspect(store);
  if (state.state !== 'FAULT') throw new Rejected('NOT_FAULTED', 'No simulation fault is latched.');
  if (state.policyHash !== POLICY_HASH) throw new Rejected('POLICY_CHANGED', 'Reset cannot approve or activate a changed policy.');
  // Audit before reset, so logging failure leaves the latch intact.
  store.audit({ action: 'simulation-fault-reset', reason, previousFault: state.fault,
    previousRunId: state.runId, policyHash: POLICY_HASH, at: new Date().toISOString() });
  const reset: PersistentState = { ...state, state: 'OFF', fault: null, runId: null, updatedAt: new Date().toISOString() };
  store.save(reset);
  return reset;
}

export function simulate(store: Store, task: Task, sim: Simulator): RunResult {
  let state = inspect(store);
  const runId = randomUUID();
  let journal: Journal | undefined;
  let fault = state.fault;
  let previousMetric: Metric | null = null;
  let proposals: Proposal[] = [];
  let usage: Usage = { contextTokens: 0, outputTokens: 0, totalTokens: 0, toolCalls: 0, failures: 0, progress: 0 };
  let outcome: RunResult['status'] = 'succeeded';
  let code = 'COMPLETED';
  let persistenceFailed = false;
  const persist = () => { state.updatedAt = new Date().toISOString(); store.save(state); };
  const event = (kind: string, data: Record<string, unknown> = {}) =>
    journal!.append({ runId, taskId: task.id, atMs: sim.nowMs, state: state.state, kind, ...data });
  const trip = (reason: string, detail: string) => {
    if (fault) { event('additional-fault', { code: reason, detail }); return; }
    fault = { code: reason, atMs: sim.nowMs, detail };
    state = { ...state, state: 'FAULT', fault };
    // Latch before cleanup or journal operations. Never transiently persist OFF after a trip.
    persist(); event('fault', { fault });
  };
  const transition = (to: State) => {
    if (fault) return;
    if (!nextStates[state.state].includes(to)) throw new Error(`Invalid transition ${state.state} -> ${to}`);
    const from = state.state;
    state.state = to; persist(); event('transition', { from, to });
  };
  const cool = (m: Metric) => m.gpuC <= POLICY.gpuResumeC && m.cpuC <= POLICY.cpuResumeC && m.gpuPowerW <= POLICY.gpuResumePowerW;
  const monitor = (): Metric | null => {
    const m = sim.sample();
    event('metric', { metric: m });
    if (!m) { trip('TELEMETRY_MISSING', 'Required synthetic telemetry is missing.'); return null; }
    const finite = [m.atMs, m.sequence, m.cpuC, m.gpuC, m.gpuPowerW, m.gpuMemoryMiB, m.ramUsedMiB].every(Number.isFinite);
    if (!finite || !Number.isSafeInteger(m.sequence) || m.sequence <= 0 || m.atMs < 0 ||
        m.cpuC < -20 || m.gpuC < -20 || m.gpuPowerW < 0 || m.gpuMemoryMiB < 0 || m.ramUsedMiB < 0 ||
        typeof m.acConnected !== 'boolean' || typeof m.thermalThrottle !== 'boolean') {
      trip('TELEMETRY_INVALID', 'Synthetic telemetry is invalid.'); return null;
    }
    if (m.atMs > sim.nowMs || sim.nowMs - m.atMs > POLICY.maxSampleAgeMs ||
        (previousMetric && (m.sequence <= previousMetric.sequence || m.atMs < previousMetric.atMs))) {
      trip('TELEMETRY_STALE', 'Synthetic telemetry is stale, future-dated, or replayed.'); return null;
    }
    previousMetric = m;
    const reasons: [boolean, string][] = [
      [m.gpuC >= POLICY.gpuTripC, 'GPU_TEMPERATURE'], [m.cpuC >= POLICY.cpuTripC, 'CPU_TEMPERATURE'],
      [m.gpuPowerW >= POLICY.gpuPowerTripW, 'GPU_POWER'], [m.gpuMemoryMiB >= POLICY.gpuMemoryTripMiB, 'VRAM_LIMIT'],
      [m.ramUsedMiB >= POLICY.ramTripMiB, 'RAM_LIMIT'], [!m.acConnected, 'AC_LOST'], [m.thermalThrottle, 'THERMAL_THROTTLE'],
    ];
    for (const [hit, reason] of reasons) if (hit) { trip(reason, 'Synthetic safety limit reached.'); break; }
    return m;
  };
  const tick = () => {
    sim.advance(); monitor();
    if (sim.nowMs >= POLICY.sessionMs) trip('SESSION_DEADLINE', 'Total simulated session deadline reached.');
  };
  const safeCleanup = () => {
    // Each wait is bounded and monitoring continues after a fault. Strata stop is
    // attempted even if worker shutdown fails. No process killing is implemented.
    if (!sim.workerStarted && !sim.strataStarted) return;
    transition('STOPPING_WORKER');
    event('cleanup-request', { target: 'worker', simulated: true });
    sim.requestWorkerStop();
    let deadline = sim.nowMs + POLICY.stopWorkerMs;
    while (!sim.pollWorkerStopped() && sim.nowMs < deadline) tick();
    if (!sim.pollWorkerStopped()) trip('WORKER_STOP_TIMEOUT', 'Synthetic worker did not acknowledge shutdown.');
    transition('STOPPING_STRATA');
    event('cleanup-request', { target: 'strata', simulated: true });
    sim.requestStrataStop();
    deadline = sim.nowMs + POLICY.stopStrataMs;
    while (!sim.pollStrataStopped() && sim.nowMs < deadline) tick();
    if (!sim.pollStrataStopped()) trip('STRATA_STOP_TIMEOUT', 'Synthetic Strata did not acknowledge shutdown.');
    transition('COOLDOWN');
    sim.beginCooldown();
    deadline = sim.nowMs + POLICY.cooldownMs;
    let coolSamples = 0;
    while (coolSamples < POLICY.cooldownSamples && sim.nowMs < deadline) {
      sim.advance();
      const sample = monitor();
      coolSamples = sample && cool(sample) ? coolSamples + 1 : 0;
    }
    if (coolSamples < POLICY.cooldownSamples) trip('COOLDOWN_TIMEOUT', 'Synthetic cooldown did not meet the stable recovery band.');
    // Keep COOLDOWN durable until the structured result is written. A crash in
    // finalization must not leave an OFF marker with a missing result.
  };
  try {
    journal = store.journal(runId);
    event('run-requested', { policyHash: POLICY_HASH, scenario: sim.scenario });
    if (state.state === 'FAULT') {
      outcome = 'rejected'; code = 'FAULT_LATCHED';
      event('run-rejected', { code, fault });
    } else {
      state.runId = runId;
      transition('PREFLIGHT');
      if (!sim.preflight()) trip('OWNERSHIP_CONFLICT', 'Synthetic existing Strata or worker detected; do not adopt or terminate it.');
      for (let i = 0; i < POLICY.preflightSamples && !fault; i++) {
        const m = monitor();
        if (m && !cool(m) && !fault) trip('PREFLIGHT_NOT_COOL', 'Synthetic preflight is outside the cool admission band.');
        if (i + 1 < POLICY.preflightSamples && !fault) sim.advance();
      }
      if (!fault) {
        transition('STARTING'); sim.startStrata(); event('simulated-start', { target: 'strata' });
        const start = sim.nowMs;
        while (!fault) {
          tick();
          if (fault) break;
          if (sim.nowMs - start >= POLICY.startupMs) { trip('STARTUP_TIMEOUT', 'Synthetic readiness deadline reached.'); break; }
          if (sim.ready()) break;
        }
      }
      if (!fault) {
        transition('RUNNING'); sim.startWorker(task); event('simulated-start', { target: 'worker' });
        const start = sim.nowMs;
        let lastProgressAt = start;
        for (;;) {
          tick();
          if (fault) break;
          if (sim.cancelled()) { outcome = 'failed'; code = 'CANCELLED'; event('cancelled'); break; }
          if (sim.nowMs - start >= POLICY.taskMs) { trip('TASK_DEADLINE', 'Synthetic task deadline reached.'); break; }
          const snapshot = sim.worker(task);
          const u = snapshot.usage;
          const keys = Object.keys(usage) as (keyof Usage)[];
          if (keys.some(k => !Number.isSafeInteger(u[k]) || u[k] < 0) ||
              (['outputTokens', 'totalTokens', 'toolCalls', 'failures', 'progress'] as const).some(k => u[k] < usage[k]) ||
              u.totalTokens < u.outputTokens || u.totalTokens < u.contextTokens) {
            trip('USAGE_INVALID', 'Usage counters are invalid or regressed.'); break;
          }
          if (u.progress > usage.progress) lastProgressAt = sim.nowMs;
          usage = { ...u }; event('usage', { usage });
          if (u.contextTokens + POLICY.maxOutputTokens > POLICY.contextTokens ||
              u.outputTokens > POLICY.maxOutputTokens || u.totalTokens > POLICY.maxTotalTokens) {
            trip('TOKEN_LIMIT', 'Synthetic context or token allowance exceeded.'); break;
          }
          if (u.toolCalls > POLICY.maxToolCalls) { trip('TOOL_LIMIT', 'Synthetic tool allowance exceeded.'); break; }
          if (u.failures > POLICY.maxFailures) { trip('FAILURE_LOOP', 'Synthetic repeated failure limit exceeded.'); break; }
          if (sim.nowMs - lastProgressAt >= POLICY.stallMs) { trip('WORKER_STALL', 'Synthetic progress deadline reached.'); break; }
          if (snapshot.done) {
            const p = snapshot.proposals;
            if (!Array.isArray(p) || p.length > POLICY.maxWritableFiles ||
                p.some(x => !x || typeof x.file !== 'string' || typeof x.patch !== 'string' ||
                  !task.writableFiles.includes(x.file)) ||
                new Set(p.map(x => x.file.toLowerCase())).size !== p.length ||
                p.reduce((n, x) => n + Buffer.byteLength(x.patch), 0) > POLICY.maxPatchBytes) {
              trip('OUTPUT_SCOPE', 'Synthetic patch is outside the file allowlist or patch budget.'); break;
            }
            if (snapshot.exitCode !== 0) { outcome = 'failed'; code = 'WORKER_FAILED'; }
            else proposals = p;
            break;
          }
        }
      }
      safeCleanup();
    }
  } catch (error) {
    // Treat exceptions and storage failures as faults. Never report success when an
    // audit/state write failed. Best-effort shutdown does not depend on journal I/O.
    const detail = error instanceof Error ? error.message.slice(0, 512) : 'Unexpected simulation error';
    fault ??= { code: 'INTERNAL_ERROR', atMs: sim.nowMs, detail };
    state = { ...state, state: 'FAULT', fault };
    try { persist(); } catch { persistenceFailed = true; }
    try { journal?.append({ kind: 'exception', runId, atMs: sim.nowMs, fault }); } catch { persistenceFailed = true; }
    sim.requestWorkerStop();
    const fallbackTick = () => { sim.advance(); try { monitor(); } catch { persistenceFailed = true; } };
    for (let i = 0; i < POLICY.stopWorkerMs / POLICY.sampleMs && !sim.pollWorkerStopped(); i++) fallbackTick();
    sim.requestStrataStop();
    for (let i = 0; i < POLICY.stopStrataMs / POLICY.sampleMs && !sim.pollStrataStopped(); i++) fallbackTick();
  }
  if (fault && outcome !== 'rejected') { outcome = 'fault'; code = fault.code; }
  if (outcome !== 'succeeded') proposals = [];
  const result: RunResult = {
    version: 1, mode: 'simulation', runId, taskId: task.id, status: outcome,
    state: state.state === 'COOLDOWN' && !fault ? 'OFF' : state.state, policyHash: POLICY_HASH, elapsedMs: sim.nowMs, fault, code,
    usage, proposals, simulated: true,
    processes: { workerStopped: sim.workerStopped, strataStopped: sim.strataStopped },
    artifacts: { events: path.join(store.directory, `${runId}.events.jsonl`), result: path.join(store.directory, `${runId}.result.json`) },
  };
  try {
    if (persistenceFailed) throw new Error('Audit/state persistence failed. Preserve state and investigate manually.');
    event('result', { status: outcome, code, processes: result.processes });
    store.atomic(`${runId}.result.json`, result);
    if (state.state === 'COOLDOWN' && !fault) transition('OFF');
  } catch (error) {
    fault ??= { code: 'PERSISTENCE_FAILURE', atMs: sim.nowMs, detail: 'Could not persist the final structured result.' };
    state = { ...state, state: 'FAULT', fault };
    try { persist(); } catch { /* Existing active state also blocks future admission. */ }
    // If the result was staged but the final state commit failed, invalidate that
    // receipt as well when storage permits. The CLI still returns an error.
    try { store.atomic(`${runId}.result.json`, { ...result, status: 'fault', state: 'FAULT',
      code: fault.code, fault, proposals: [] }); } catch { /* Preserve partial evidence. */ }
    throw error;
  } finally { journal?.close(); }
  return result;
}
