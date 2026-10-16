import { closeSync, existsSync, fsyncSync, lstatSync, mkdirSync, openSync,
  readSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { POLICY_HASH, Rejected, record, type PersistentState } from './contracts.js';

export class Busy extends Error {}
export function readJson(file: string, maxBytes = 65536): unknown {
  // Bound allocation/read, even if the input grows after stat or is not a regular file.
  if (!lstatSync(file).isFile()) throw new Rejected('INVALID_INPUT', 'Expected a regular JSON file.');
  const fd = openSync(file, 'r');
  try {
    const data = Buffer.alloc(maxBytes + 1);
    let used = 0, n = 0;
    do { n = readSync(fd, data, used, data.length - used, null); used += n; } while (n && used < data.length);
    if (used > maxBytes) throw new Rejected('INPUT_LIMIT', 'JSON file exceeds size limit.');
    return JSON.parse(data.subarray(0, used).toString('utf8'));
  } finally { closeSync(fd); }
}
function noLinks(dir: string) {
  let current = path.resolve(dir);
  for (;;) {
    if (existsSync(current) && lstatSync(current).isSymbolicLink())
      throw new Rejected('STATE_PATH', 'State directories must not contain symlinks or junctions.');
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
}
export function freshState(): PersistentState {
  return { version: 1, mode: 'simulation', state: 'OFF', policyHash: POLICY_HASH,
    runId: null, fault: null, updatedAt: new Date().toISOString() };
}
export class Store {
  readonly directory: string;
  private locked = false;
  constructor(dir: string) { this.directory = path.resolve(dir); }
  acquire() {
    noLinks(this.directory);
    mkdirSync(this.directory, { recursive: true });
    noLinks(this.directory);
    const lock = path.join(this.directory, 'supervisor.lock');
    let fd: number;
    try { fd = openSync(lock, 'wx', 0o600); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'EEXIST')
        throw new Busy('Supervisor lock exists. Do not auto-delete it; inspect its owner before manual stale-lock recovery.');
      throw error;
    }
    try { writeFileSync(fd, JSON.stringify({ mode: 'simulation', pid: process.pid, createdAt: new Date().toISOString() })); fsyncSync(fd); }
    catch (error) { closeSync(fd); unlinkSync(lock); throw error; }
    closeSync(fd);
    this.locked = true;
  }
  release() {
    if (this.locked) { unlinkSync(path.join(this.directory, 'supervisor.lock')); this.locked = false; }
  }
  private assertLocked() { if (!this.locked) throw new Error('State mutation requires the supervisor lock.'); }
  load(): PersistentState {
    this.assertLocked();
    const file = path.join(this.directory, 'state.json');
    if (!existsSync(file)) return freshState();
    const s = readJson(file);
    const states = ['OFF', 'PREFLIGHT', 'STARTING', 'RUNNING', 'STOPPING_WORKER', 'STOPPING_STRATA', 'COOLDOWN', 'FAULT'];
    if (!record(s) || s.version !== 1 || s.mode !== 'simulation' || typeof s.policyHash !== 'string' ||
        !states.includes(String(s.state)) || typeof s.updatedAt !== 'string' ||
        !(s.runId === null || typeof s.runId === 'string') ||
        !(s.fault === null || (record(s.fault) && typeof s.fault.code === 'string' && typeof s.fault.detail === 'string' &&
          typeof s.fault.atMs === 'number' && Number.isFinite(s.fault.atMs) && s.fault.atMs >= 0)) ||
        (s.state === 'FAULT') !== (s.fault !== null))
      throw new Rejected('STATE_CORRUPT', 'State is corrupt; preserve the file and require manual recovery.');
    return s as unknown as PersistentState;
  }
  save(state: PersistentState) { this.atomic('state.json', state); }
  atomic(name: string, value: unknown) {
    this.assertLocked();
    if (!/^[A-Za-z0-9_.-]+$/.test(name)) throw new Error('Invalid artifact name.');
    const tmp = path.join(this.directory, `${name}.${randomUUID()}.tmp`);
    const fd = openSync(tmp, 'wx', 0o600);
    try { writeFileSync(fd, JSON.stringify(value, null, 2) + '\n'); fsyncSync(fd); }
    finally { closeSync(fd); }
    try { renameSync(tmp, path.join(this.directory, name)); }
    catch (error) { unlinkSync(tmp); throw error; }
  }
  journal(runId: string) {
    this.assertLocked();
    return new Journal(path.join(this.directory, `${runId}.events.jsonl`));
  }
  audit(event: unknown) {
    this.assertLocked();
    // A separate record per operator action avoids an unbounded global append file.
    this.atomic(`audit-${randomUUID()}.json`, event);
  }
}
export class Journal {
  private fd: number;
  private bytes = 0;
  private sequence = 0;
  constructor(readonly file: string) { this.fd = openSync(file, 'wx', 0o600); }
  append(event: Record<string, unknown>) {
    const line = JSON.stringify({ version: 1, mode: 'simulation', sequence: ++this.sequence,
      recordedAt: new Date().toISOString(), ...event }) + '\n';
    this.bytes += Buffer.byteLength(line);
    if (this.bytes > 2 * 1024 * 1024) throw new Error('Per-run event log limit exceeded.');
    writeFileSync(this.fd, line); fsyncSync(this.fd);
  }
  close() { if (this.fd !== -1) { closeSync(this.fd); this.fd = -1; } }
}
