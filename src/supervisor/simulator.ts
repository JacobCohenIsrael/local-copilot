import { POLICY, type Metric, type Proposal, type Task, type Usage } from './contracts.js';

export const SCENARIOS = ['happy', 'gpu-hot', 'cpu-hot', 'power-spike', 'vram-high', 'ram-high',
  'sensor-missing', 'sensor-stale', 'ac-lost', 'thermal-throttle', 'preflight-hot',
  'startup-timeout', 'worker-failure', 'worker-stall', 'task-timeout', 'context-overflow',
  'token-overflow', 'tool-overflow', 'failure-loop', 'file-escape', 'patch-overflow',
  'worker-stop-timeout', 'strata-stop-timeout', 'cooldown-timeout', 'cancel',
  'adapter-error', 'already-running'] as const;
export type Scenario = typeof SCENARIOS[number];
export interface WorkerSnapshot { usage: Usage; done: boolean; exitCode: number; proposals: Proposal[] }
// This is a fake resource model, not a pluggable process adapter. No command or HTTP execution exists.
export class Simulator {
  readonly mode = 'simulation';
  nowMs = 0;
  workerStarted = false;
  strataStarted = false;
  workerStopped = true;
  strataStopped = true;
  readonly calls: string[] = [];
  private startAt = 0;
  private workAt = 0;
  private workerStopAt: number | null = null;
  private strataStopAt: number | null = null;
  private seq = 0;
  private cooling = false;
  constructor(readonly scenario: Scenario) {}
  advance() { this.nowMs += POLICY.sampleMs; }
  preflight() { this.calls.push('preflight'); return this.scenario !== 'already-running'; }
  sample(): Metric | null {
    const active = this.workerStarted && !this.workerStopped;
    const trigger = this.workerStarted && this.nowMs - this.workAt >= 2000;
    const m: Metric = { sequence: ++this.seq, atMs: this.nowMs,
      cpuC: active ? 58 : 45, gpuC: active ? 55 : 40, gpuPowerW: active ? 65 : 20,
      gpuMemoryMiB: active ? 10000 : 1024, ramUsedMiB: 8192,
      acConnected: true, thermalThrottle: false };
    if (trigger) {
      switch (this.scenario) {
        case 'gpu-hot': m.gpuC = POLICY.gpuTripC; break;
        case 'cpu-hot': m.cpuC = POLICY.cpuTripC; break;
        case 'power-spike': m.gpuPowerW = POLICY.gpuPowerTripW; break;
        case 'vram-high': m.gpuMemoryMiB = POLICY.gpuMemoryTripMiB; break;
        case 'ram-high': m.ramUsedMiB = POLICY.ramTripMiB; break;
        case 'sensor-missing': return null;
        case 'sensor-stale': m.atMs -= POLICY.maxSampleAgeMs + 1; break;
        case 'ac-lost': m.acConnected = false; break;
        case 'thermal-throttle': m.thermalThrottle = true; break;
      }
    }
    if (this.scenario === 'preflight-hot' || (this.cooling && this.scenario === 'cooldown-timeout')) m.gpuC = 65;
    return m;
  }
  startStrata() {
    this.calls.push('start-strata'); this.startAt = this.nowMs;
    this.strataStarted = true; this.strataStopped = false;
  }
  ready() { return this.scenario !== 'startup-timeout' && this.nowMs - this.startAt >= 2000; }
  startWorker(_task: Task) {
    this.calls.push('start-worker'); this.workAt = this.nowMs;
    this.workerStarted = true; this.workerStopped = false;
  }
  worker(task: Task): WorkerSnapshot {
    if (this.scenario === 'adapter-error') throw new Error('Synthetic adapter failure');
    const tick = Math.max(0, Math.floor((this.nowMs - this.workAt) / POLICY.sampleMs));
    const usage: Usage = { contextTokens: 1200, outputTokens: tick * 10,
      totalTokens: 1200 + tick * 10, toolCalls: 1, failures: 0,
      progress: this.scenario === 'worker-stall' ? 0 : tick };
    switch (this.scenario) {
      case 'context-overflow': usage.contextTokens = POLICY.contextTokens + 1; usage.totalTokens = usage.contextTokens + usage.outputTokens; break;
      case 'token-overflow': usage.totalTokens = POLICY.maxTotalTokens + 1; break;
      case 'tool-overflow': usage.toolCalls = POLICY.maxToolCalls + 1; break;
      case 'failure-loop': usage.failures = POLICY.maxFailures + 1; break;
    }
    const done = !['worker-stall', 'task-timeout'].includes(this.scenario) && tick >= 4;
    return { usage, done, exitCode: this.scenario === 'worker-failure' ? 1 : 0,
      proposals: done ? [{ file: this.scenario === 'file-escape' ? '../outside.ts' : task.writableFiles[0],
        patch: this.scenario === 'patch-overflow' ? 'x'.repeat(POLICY.maxPatchBytes + 1) :
          'SIMULATED PROPOSAL ONLY: replace multiplication with division after review.' }] : [] };
  }
  cancelled() { return this.scenario === 'cancel' && this.workerStarted && this.nowMs - this.workAt >= 2000; }
  requestWorkerStop() { this.calls.push('stop-worker'); this.workerStopAt ??= this.nowMs; }
  requestStrataStop() { this.calls.push('stop-strata'); this.strataStopAt ??= this.nowMs; }
  pollWorkerStopped() {
    if (this.workerStopped) return true;
    if (this.workerStopAt !== null && this.scenario !== 'worker-stop-timeout' && this.nowMs - this.workerStopAt >= 1000)
      this.workerStopped = true;
    return this.workerStopped;
  }
  pollStrataStopped() {
    if (this.strataStopped) return true;
    if (this.strataStopAt !== null && this.scenario !== 'strata-stop-timeout' && this.nowMs - this.strataStopAt >= 1000)
      this.strataStopped = true;
    return this.strataStopped;
  }
  beginCooldown() { this.cooling = true; this.calls.push('cooldown'); }
}
