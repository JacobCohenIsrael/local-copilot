import { createHash } from 'node:crypto';

export const VERSION = 1;
// Provisional simulator values only. No claim that these are safe for this laptop.
export const POLICY = Object.freeze({
  id: 'simulation-v1', mode: 'simulation-only', policyChanges: 'human-review-required',
  maxTaskBytes: 1024, maxContextFiles: 4, maxFileBytes: 4096,
  maxContextBytes: 2048, maxWritableFiles: 2, maxPatchBytes: 8192,
  contextTokens: 4096, reservedTokens: 512, maxOutputTokens: 1024,
  maxTotalTokens: 8192, maxToolCalls: 8, maxFailures: 1,
  sampleMs: 1000, maxSampleAgeMs: 2000, preflightSamples: 3,
  startupMs: 30000, taskMs: 60000, stallMs: 15000,
  stopWorkerMs: 5000, stopStrataMs: 5000, cooldownMs: 10000,
  sessionMs: 120000, cooldownSamples: 3,
  gpuTripC: 75, cpuTripC: 85, gpuPowerTripW: 100,
  gpuMemoryTripMiB: 14336, ramTripMiB: 28672,
  gpuResumeC: 60, cpuResumeC: 70, gpuResumePowerW: 40,
});
export const POLICY_HASH = createHash('sha256').update(JSON.stringify(POLICY)).digest('hex');
export type State = 'OFF' | 'PREFLIGHT' | 'STARTING' | 'RUNNING' |
  'STOPPING_WORKER' | 'STOPPING_STRATA' | 'COOLDOWN' | 'FAULT';
export interface Task {
  version: 1;
  id: string;
  instruction: string;
  context: { file: string; content: string }[];
  writableFiles: string[];
}
export interface Fault { code: string; atMs: number; detail: string }
export interface PersistentState {
  version: 1; mode: 'simulation'; state: State; policyHash: string;
  runId: string | null; fault: Fault | null; updatedAt: string;
}
export interface Metric {
  sequence: number; atMs: number; cpuC: number; gpuC: number;
  gpuPowerW: number; gpuMemoryMiB: number; ramUsedMiB: number;
  acConnected: boolean; thermalThrottle: boolean;
}
export interface Usage {
  contextTokens: number; outputTokens: number; totalTokens: number;
  toolCalls: number; failures: number; progress: number;
}
export interface Proposal { file: string; patch: string }
export interface RunResult {
  version: 1; mode: 'simulation'; runId: string; taskId: string;
  status: 'succeeded' | 'failed' | 'fault' | 'rejected'; state: State;
  policyHash: string; elapsedMs: number; fault: Fault | null;
  code: string; usage: Usage; proposals: Proposal[];
  processes: { workerStopped: boolean; strataStopped: boolean };
  simulated: true; artifacts: { events: string; result: string };
}
export class Rejected extends Error {
  constructor(public code: string, message: string) { super(message); }
}
export function record(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}
export function exactKeys(value: Record<string, unknown>, keys: string[]) {
  if (Object.keys(value).length !== keys.length || keys.some(k => !(k in value)))
    throw new Rejected('INVALID_SCHEMA', 'Unexpected or missing fields. Policy overrides and commands are not accepted.');
}
const bytes = (s: string) => Buffer.byteLength(s, 'utf8');
export function safeFile(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 160) return false;
  const parts = value.split('/');
  return parts.every(p => /^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(p) &&
    !p.endsWith('.') && !/^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)/i.test(p) &&
    !/^(node_modules|vendor|dist|build|target|coverage)$/i.test(p) &&
    !/(secret|credential|password|token|private[-_]?key)/i.test(p)) &&
    /\.(ts|tsx|js|jsx|json|md|txt|py|css|html)$/i.test(value);
}
export function validateTask(value: unknown): Task {
  if (!record(value)) throw new Rejected('INVALID_TASK', 'Task must be an object.');
  exactKeys(value, ['version', 'id', 'instruction', 'context', 'writableFiles']);
  if (value.version !== VERSION || typeof value.id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(value.id) ||
      typeof value.instruction !== 'string' || !value.instruction.trim() || bytes(value.instruction) > POLICY.maxTaskBytes)
    throw new Rejected('INVALID_TASK', 'Invalid task version, id, or instruction size.');
  if (!Array.isArray(value.context) || value.context.length > POLICY.maxContextFiles ||
      !Array.isArray(value.writableFiles) || !value.writableFiles.length || value.writableFiles.length > POLICY.maxWritableFiles)
    throw new Rejected('FILE_LIMIT', 'Context or writable file count exceeds policy.');
  let contextBytes = 0;
  const names = new Set<string>();
  for (const c of value.context) {
    if (!record(c)) throw new Rejected('INVALID_CONTEXT', 'Context must contain file/content pairs.');
    exactKeys(c, ['file', 'content']);
    if (!safeFile(c.file) || typeof c.content !== 'string' || c.content.includes('\0') || bytes(c.content) > POLICY.maxFileBytes)
      throw new Rejected('INVALID_CONTEXT', 'Invalid file path, content, or size.');
    if (names.has(c.file.toLowerCase())) throw new Rejected('DUPLICATE_FILE', 'Windows paths are case insensitive.');
    names.add(c.file.toLowerCase());
    contextBytes += bytes(c.content) + bytes(c.file);
  }
  if (contextBytes > POLICY.maxContextBytes) throw new Rejected('CONTEXT_LIMIT', 'Context bytes exceed policy.');
  const writes = value.writableFiles;
  if (!writes.every(safeFile) || new Set(writes.map(f => f.toLowerCase())).size !== writes.length)
    throw new Rejected('INVALID_WRITABLE_FILES', 'Writable paths must be unique, relative source file names.');
  // Byte count plus envelope reservation is an intentionally conservative admission proxy.
  // Real adapters must tokenize the complete prompt and tool history with the actual tokenizer.
  const admissionTokens = bytes(JSON.stringify(value)) + POLICY.reservedTokens;
  if (admissionTokens + POLICY.maxOutputTokens > POLICY.contextTokens)
    throw new Rejected('CONTEXT_LIMIT', 'Task envelope plus reserved output exceeds context budget.');
  return structuredClone(value) as unknown as Task;
}
export function plan(task: Task) {
  return {
    version: VERSION, mode: 'simulation', taskId: task.id, policyHash: POLICY_HASH,
    admissionTokenUpperBound: bytes(JSON.stringify(task)) + POLICY.reservedTokens,
    policy: POLICY, states: ['OFF', 'PREFLIGHT', 'STARTING', 'RUNNING', 'STOPPING_WORKER', 'STOPPING_STRATA', 'COOLDOWN', 'OFF'],
    liveExecutionAvailable: false,
    target: { platform: 'Windows', strataLauncher: 'D:\\AI\\run-coder-iq1_m.bat',
      endpoint: 'http://localhost:8080/v1', model: 'Qwen3.8 Flash Next Coder IQ1_M', worker: 'OpenCode' },
    actions: ['Read supplied inline context only', 'Simulate Strata startup and one bounded task',
      'Record synthetic metrics', 'Return simulated patch proposals', 'Simulate worker then Strata shutdown'],
  };
}
