import test, { type TestContext } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, readdirSync, writeFileSync, rmSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { POLICY, POLICY_HASH, plan, validateTask, type Metric, type PersistentState, type Task } from '../src/supervisor/contracts.js';
import { Simulator, SCENARIOS, type Scenario } from '../src/supervisor/simulator.js';
import { Busy, Store, freshState, readJson } from '../src/supervisor/store.js';
import { inspect, resetFault, simulate } from '../src/supervisor/supervisor.js';

const task: Task = { version: 1, id: 'test-task', instruction: 'Fix arithmetic in this file only.',
  context: [{ file: 'src/math.ts', content: 'export const divide = (a,b) => a*b;' }], writableFiles: ['src/math.ts'] };
function fixture(t: TestContext) {
  const root = mkdtempSync(path.join(os.tmpdir(), 'copilot-supervisor-test-'));
  t.after(() => {
    const relative = path.relative(os.tmpdir(), root);
    assert.ok(relative.startsWith('copilot-supervisor-test-') && !relative.includes(path.sep));
    rmSync(root, { recursive: true, force: true });
  });
  return root;
}
function locked<T>(directory: string, fn: (store: Store) => T): T {
  const store = new Store(directory); store.acquire();
  try { return fn(store); } finally { store.release(); }
}
const cli = fileURLToPath(new URL('../src/supervisor-cli.js', import.meta.url));
const invoke = (args: string[]) => {
  const result = spawnSync(process.execPath, [cli, ...args], { encoding: 'utf8', windowsHide: true, timeout: 10000 });
  assert.equal(result.error, undefined);
  return { code: result.status, stdout: result.stdout, stderr: result.stderr };
};

test('happy lifecycle admits exactly one task, monitors shutdown, and returns only simulated proposals', t => {
  const root = fixture(t), sim = new Simulator('happy');
  const result = locked(root, store => simulate(store, validateTask(task), sim));
  assert.equal(result.status, 'succeeded'); assert.equal(result.state, 'OFF');
  assert.equal(result.simulated, true); assert.equal(result.mode, 'simulation');
  assert.deepEqual(sim.calls, ['preflight', 'start-strata', 'start-worker', 'stop-worker', 'stop-strata', 'cooldown']);
  assert.deepEqual(result.processes, { workerStopped: true, strataStopped: true });
  assert.equal(result.proposals[0].file, 'src/math.ts');
  const events = readFileSync(result.artifacts.events, 'utf8').trim().split('\n').map(s => JSON.parse(s));
  assert.deepEqual(events.filter(e => e.kind === 'transition').map(e => e.to),
    ['PREFLIGHT', 'STARTING', 'RUNNING', 'STOPPING_WORKER', 'STOPPING_STRATA', 'COOLDOWN', 'OFF']);
  assert.ok(events.some(e => e.kind === 'metric' && e.state === 'STOPPING_STRATA'));
  assert.ok(events.every((e, i) => e.sequence === i + 1 && e.runId === result.runId && e.mode === 'simulation'));
  assert.deepEqual(JSON.parse(readFileSync(result.artifacts.result, 'utf8')), result);
  assert.ok(!readdirSync(root).includes('supervisor.lock'));
});

const faultScenarios: Partial<Record<Scenario, string>> = {
  'gpu-hot': 'GPU_TEMPERATURE', 'cpu-hot': 'CPU_TEMPERATURE', 'power-spike': 'GPU_POWER',
  'vram-high': 'VRAM_LIMIT', 'ram-high': 'RAM_LIMIT', 'sensor-missing': 'TELEMETRY_MISSING',
  'sensor-stale': 'TELEMETRY_STALE', 'ac-lost': 'AC_LOST', 'thermal-throttle': 'THERMAL_THROTTLE',
  'preflight-hot': 'PREFLIGHT_NOT_COOL', 'startup-timeout': 'STARTUP_TIMEOUT', 'worker-stall': 'WORKER_STALL',
  'task-timeout': 'TASK_DEADLINE', 'context-overflow': 'TOKEN_LIMIT', 'token-overflow': 'TOKEN_LIMIT',
  'tool-overflow': 'TOOL_LIMIT', 'failure-loop': 'FAILURE_LOOP', 'file-escape': 'OUTPUT_SCOPE',
  'patch-overflow': 'OUTPUT_SCOPE', 'worker-stop-timeout': 'WORKER_STOP_TIMEOUT',
  'strata-stop-timeout': 'STRATA_STOP_TIMEOUT', 'cooldown-timeout': 'COOLDOWN_TIMEOUT',
  'adapter-error': 'INTERNAL_ERROR', 'already-running': 'OWNERSHIP_CONFLICT',
};
for (const [scenario, expected] of Object.entries(faultScenarios)) {
  test(`${scenario}: durable fault blocks another process session`, t => {
    const root = fixture(t), sim = new Simulator(scenario as Scenario);
    const result = locked(root, store => simulate(store, task, sim));
    assert.equal(result.status, 'fault'); assert.equal(result.state, 'FAULT'); assert.equal(result.code, expected);
    assert.equal(result.proposals.length, 0); assert.ok(result.elapsedMs <= POLICY.sessionMs);
    const next = new Simulator('happy');
    const blocked = locked(root, store => simulate(store, task, next));
    assert.equal(blocked.status, 'rejected'); assert.equal(blocked.code, 'FAULT_LATCHED');
    assert.deepEqual(next.calls, []);
    assert.equal(locked(root, inspect).fault?.code, expected);
    if (sim.strataStarted) assert.ok(sim.calls.includes('stop-strata'));
  });
}

for (const scenario of ['cancel', 'worker-failure'] as const) {
  test(`${scenario}: bounded task failure cleans up without a safety latch`, t => {
    const sim = new Simulator(scenario);
    const result = locked(fixture(t), store => simulate(store, task, sim));
    assert.equal(result.status, 'failed'); assert.equal(result.state, 'OFF'); assert.equal(result.fault, null);
    assert.equal(result.proposals.length, 0);
    assert.ok(result.processes.workerStopped && result.processes.strataStopped);
  });
}

test('every CLI scenario has an explicit expectation', () => {
  assert.deepEqual(new Set(SCENARIOS), new Set(['happy', 'cancel', 'worker-failure', ...Object.keys(faultScenarios)]));
});

test('fault is already persisted when worker shutdown starts, even if worker stop times out', t => {
  const root = fixture(t);
  class FaultObserver extends Simulator {
    override requestWorkerStop() {
      const state = JSON.parse(readFileSync(path.join(root, 'state.json'), 'utf8'));
      assert.equal(state.state, 'FAULT'); assert.equal(state.fault.code, 'GPU_TEMPERATURE');
      super.requestWorkerStop();
    }
    override pollWorkerStopped() { return false; }
  }
  const sim = new FaultObserver('gpu-hot');
  const result = locked(root, store => simulate(store, task, sim));
  assert.equal(result.fault?.code, 'GPU_TEMPERATURE');
  assert.equal(result.processes.workerStopped, false); assert.equal(result.processes.strataStopped, true);
  assert.ok(sim.calls.indexOf('stop-worker') < sim.calls.indexOf('stop-strata'));
});

test('reset requires deliberate acknowledgement, records review, and never runs anything', t => {
  const root = fixture(t);
  locked(root, store => simulate(store, task, new Simulator('gpu-hot')));
  locked(root, store => {
    assert.throws(() => resetFault(store, 'Reviewed synthetic trip', false), /acknowledgement/);
    assert.equal(inspect(store).state, 'FAULT');
    assert.throws(() => resetFault(store, 'short', true));
    assert.equal(resetFault(store, 'Reviewed synthetic trip and cleanup', true).state, 'OFF');
  });
  const audit = readdirSync(root).filter(n => n.startsWith('audit-')).map(n => JSON.parse(readFileSync(path.join(root, n), 'utf8')));
  assert.ok(audit.some(e => e.action === 'simulation-fault-reset' && e.previousFault.code === 'GPU_TEMPERATURE'));
  assert.equal(locked(root, store => simulate(store, task, new Simulator('happy'))).status, 'succeeded');
});

test('interrupted session is faulted on inspection and cannot automatically restart', t => {
  const root = fixture(t);
  locked(root, store => store.save({ ...freshState(), state: 'RUNNING', runId: 'old-simulated-run' }));
  assert.equal(locked(root, inspect).fault?.code, 'UNCLEAN_EXIT');
  const sim = new Simulator('happy');
  assert.equal(locked(root, store => simulate(store, task, sim)).code, 'FAULT_LATCHED');
  assert.deepEqual(sim.calls, []);
});

test('policy fingerprint changes cannot be approved by resetting a fault', t => {
  const root = fixture(t);
  locked(root, store => store.save({ ...freshState(), policyHash: 'unapproved' }));
  locked(root, store => {
    assert.equal(inspect(store).fault?.code, 'POLICY_CHANGED');
    assert.throws(() => resetFault(store, 'Reviewed synthetic fault', true), /changed policy/);
    assert.equal(inspect(store).policyHash, 'unapproved');
  });
  assert.equal(POLICY.mode, 'simulation-only'); assert.ok(Object.isFrozen(POLICY));
  assert.equal(POLICY_HASH.length, 64);
});

test('exclusive lock rejects concurrent access and never auto-clears an orphan lock', t => {
  const root = fixture(t), store = new Store(root); store.acquire();
  try {
    assert.throws(() => new Store(root).acquire(), Busy);
    const blocked = invoke(['status', '--state-dir', root]);
    assert.equal(blocked.code, 4); assert.equal(JSON.parse(blocked.stderr).error.code, 'BUSY');
  } finally { store.release(); }
  writeFileSync(path.join(root, 'supervisor.lock'), '{"pid":999999999}');
  assert.throws(() => new Store(root).acquire(), Busy);
  assert.equal(readFileSync(path.join(root, 'supervisor.lock'), 'utf8'), '{"pid":999999999}');
});

test('corrupt state is preserved and rejected before any simulated launch', t => {
  const root = fixture(t), state = path.join(root, 'state.json');
  writeFileSync(state, '{invalid');
  const sim = new Simulator('happy');
  assert.throws(() => locked(root, store => simulate(store, task, sim)));
  assert.deepEqual(sim.calls, []); assert.equal(readFileSync(state, 'utf8'), '{invalid');
  for (const invalid of [{ ...freshState(), state: 'OFF', fault: { code: 'x', detail: 'x', atMs: 0 } },
    { ...freshState(), state: 'FAULT' }]) {
    writeFileSync(state, JSON.stringify(invalid));
    assert.throws(() => locked(root, inspect), /corrupt/);
  }
});

test('missing, NaN, future, and replayed telemetry fail closed', t => {
  const mutations: ((m: Metric) => Metric)[] = [
    m => ({ ...m, cpuC: NaN }), m => ({ ...m, atMs: 999999 }),
    m => ({ ...m, sequence: 1 }), m => ({ ...m, acConnected: undefined as unknown as boolean }),
  ];
  for (const mutate of mutations) {
    class BadSensor extends Simulator {
      override sample() { const m = super.sample()!; return this.workerStarted ? mutate(m) : m; }
    }
    const result = locked(path.join(fixture(t), 'state'), store => simulate(store, task, new BadSensor('happy')));
    assert.equal(result.status, 'fault'); assert.match(result.code, /^TELEMETRY_/);
  }
});

test('regressing or unbounded worker usage trips before proposals are accepted', t => {
  for (const kind of ['regression', 'output', 'nan'] as const) {
    class BadUsage extends Simulator {
      override worker(task: Task) {
        const snapshot = super.worker(task);
        if (kind === 'regression') snapshot.usage.totalTokens = this.nowMs > 5000 ? 0 : 2000;
        if (kind === 'output') snapshot.usage.outputTokens = POLICY.maxOutputTokens + 1;
        if (kind === 'nan') snapshot.usage.toolCalls = NaN;
        return snapshot;
      }
    }
    const result = locked(fixture(t), store => simulate(store, task, new BadUsage('happy')));
    assert.equal(result.status, 'fault'); assert.equal(result.proposals.length, 0);
  }
});

test('safety monitoring also trips during startup and shutdown', t => {
  for (const phase of ['startup', 'shutdown']) {
    class PhaseTrip extends Simulator {
      override sample() {
        const m = super.sample()!;
        if ((phase === 'startup' && this.strataStarted && !this.workerStarted) ||
            (phase === 'shutdown' && this.calls.includes('stop-worker'))) m.gpuC = POLICY.gpuTripC;
        return m;
      }
    }
    const sim = new PhaseTrip('happy');
    const result = locked(fixture(t), store => simulate(store, task, sim));
    assert.equal(result.code, 'GPU_TEMPERATURE'); assert.equal(result.status, 'fault');
    if (phase === 'startup') assert.equal(sim.workerStarted, false);
    assert.equal(result.processes.strataStopped, true);
  }
});

test('task schema and Windows paths cannot broaden the task or policy', () => {
  assert.deepEqual(validateTask(task), task);
  for (const file of ['../escape.ts', '/abs.ts', 'C:/abs.ts', 'foo\\bar.ts', 'file.ts:ads', '.env', '.git/config',
    'CON.ts', 'nested/aux.txt', 'lpt1.txt', 'nested/secrets.json', 'node_modules/x.ts', 'foo./x.ts', 'script.bat', '']) {
    assert.throws(() => validateTask({ ...task, writableFiles: [file] }), file);
  }
  for (const invalid of [
    { ...task, policy: { gpuTripC: 120 } }, { ...task, command: 'run arbitrary command' },
    { ...task, instruction: 'x'.repeat(POLICY.maxTaskBytes + 1) },
    { ...task, context: [{ file: 'a.ts', content: 'x'.repeat(POLICY.maxContextBytes + 1) }] },
    { ...task, context: [{ file: 'a.ts', content: '' }, { file: 'A.ts', content: '' }] },
    { ...task, context: Array.from({ length: 5 }, (_, n) => ({ file: `f${n}.ts`, content: '' })) },
    { ...task, writableFiles: ['a.ts', 'b.ts', 'c.ts'] }, { ...task, writableFiles: ['a.ts', 'A.ts'] },
    { ...task, instruction: '😀'.repeat(300) },
  ]) assert.throws(() => validateTask(invalid));
  assert.equal(plan(task).liveExecutionAvailable, false);
});

test('bounded JSON input rejects oversized files and directories', t => {
  const root = fixture(t), input = path.join(root, 'big.json');
  writeFileSync(input, ' '.repeat(65537));
  assert.throws(() => readJson(input), /size limit/);
  assert.throws(() => readJson(root), /regular JSON file/);
});

test('final result persistence failure cannot return success or leave OFF', t => {
  const root = fixture(t);
  class FailedDisk extends Store {
    override atomic(name: string, data: unknown) {
      if (name.endsWith('.result.json')) throw new Error('Synthetic disk full');
      super.atomic(name, data);
    }
  }
  const store = new FailedDisk(root); store.acquire();
  try {
    assert.throws(() => simulate(store, task, new Simulator('happy')), /disk full/);
    assert.equal(store.load().state, 'FAULT'); assert.equal(store.load().fault?.code, 'PERSISTENCE_FAILURE');
  } finally { store.release(); }
});

test('state persistence failure still requests bounded resource shutdown and reports an error', t => {
  class BrokenStore extends Store {
    broken = false;
    override save(state: PersistentState) {
      if (this.broken || state.state === 'RUNNING') { this.broken = true; throw new Error('Synthetic state disk failure'); }
      super.save(state);
    }
  }
  const store = new BrokenStore(fixture(t)); store.acquire();
  const sim = new Simulator('happy');
  try {
    assert.throws(() => simulate(store, task, sim), /persistence failed/);
    assert.equal(sim.strataStopped, true); assert.ok(sim.calls.includes('stop-strata'));
    // The durable STARTING marker still prevents future admission if a FAULT write fails.
    assert.equal(store.load().state, 'STARTING');
  } finally { store.release(); }
});

test('a final OFF commit failure invalidates an already-written success receipt', t => {
  const root = fixture(t);
  class FailedCommit extends Store {
    override save(state: PersistentState) {
      if (state.state === 'OFF') throw new Error('Synthetic final commit failure');
      super.save(state);
    }
  }
  const store = new FailedCommit(root); store.acquire();
  try {
    assert.throws(() => simulate(store, task, new Simulator('happy')), /final commit failure/);
    assert.equal(store.load().state, 'FAULT');
    const receipts = readdirSync(root).filter(n => n.endsWith('.result.json'));
    assert.equal(receipts.length, 1);
    assert.equal(JSON.parse(readFileSync(path.join(root, receipts[0]), 'utf8')).status, 'fault');
  } finally { store.release(); }
});

test('failed reset audit leaves the safety latch intact', t => {
  const root = fixture(t);
  locked(root, store => simulate(store, task, new Simulator('gpu-hot')));
  class FailedAudit extends Store { override audit() { throw new Error('Synthetic audit error'); } }
  const store = new FailedAudit(root); store.acquire();
  try {
    assert.throws(() => resetFault(store, 'Reviewed simulation fault', true), /audit error/);
    assert.equal(store.load().state, 'FAULT');
  } finally { store.release(); }
});

test('JSON CLI planning, simulation, cross-process latch, reset and live rejection', t => {
  const root = fixture(t), stateDir = path.join(root, 'state'), input = path.join(root, 'task.json');
  writeFileSync(input, JSON.stringify(task));
  const planned = invoke(['plan', '--task', input]);
  assert.equal(planned.code, 0, planned.stderr); assert.equal(JSON.parse(planned.stdout).liveExecutionAvailable, false);
  assert.deepEqual(readdirSync(root), ['task.json']);
  const good = invoke(['simulate', '--task', input, '--state-dir', stateDir]);
  assert.equal(good.code, 0, good.stderr); assert.equal(JSON.parse(good.stdout).status, 'succeeded');
  const hot = invoke(['simulate', '--task', input, '--state-dir', stateDir, '--scenario', 'gpu-hot']);
  assert.equal(hot.code, 3, hot.stderr); assert.equal(JSON.parse(hot.stdout).code, 'GPU_TEMPERATURE');
  const blocked = invoke(['simulate', '--task', input, '--state-dir', stateDir]);
  assert.equal(blocked.code, 2); assert.equal(JSON.parse(blocked.stdout).code, 'FAULT_LATCHED');
  const status = invoke(['status', '--state-dir', stateDir]);
  assert.equal(status.code, 3); assert.equal(JSON.parse(status.stdout).state, 'FAULT');
  const badReset = invoke(['reset-fault', '--state-dir', stateDir, '--reason', 'Reviewed simulation']);
  assert.equal(badReset.code, 2);
  const reset = invoke(['reset-fault', '--state-dir', stateDir, '--reason', 'Reviewed synthetic thermal fault', '--acknowledge-simulation']);
  assert.equal(reset.code, 0, reset.stderr); assert.equal(JSON.parse(reset.stdout).state, 'OFF');
  for (const args of [['run'], ['start'], ['simulate', '--live'], ['policy', '--gpu-trip', '120'],
    ['simulate', '--task', input, '--scenario', 'unknown'], ['plan', '--task', input, '--scenario', 'happy']]) {
    const rejected = invoke(args); assert.equal(rejected.code, 2, rejected.stderr);
  }
  const policy = invoke(['policy']); assert.equal(policy.code, 0); assert.equal(JSON.parse(policy.stdout).policyHash, POLICY_HASH);
});
