#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { POLICY, POLICY_HASH, Rejected, plan, validateTask } from './supervisor/contracts.js';
import { Simulator, SCENARIOS, type Scenario } from './supervisor/simulator.js';
import { Busy, Store, readJson } from './supervisor/store.js';
import { inspect, resetFault, simulate } from './supervisor/supervisor.js';

const help = `Local Copilot supervisor — SIMULATION ONLY (no Strata/OpenCode execution)

  node dist/src/supervisor-cli.js plan --task examples/supervisor/task.json
  node dist/src/supervisor-cli.js simulate --task examples/supervisor/task.json [--scenario happy]
  node dist/src/supervisor-cli.js status
  node dist/src/supervisor-cli.js reset-fault --acknowledge-simulation --reason "Reviewed synthetic fault"
  node dist/src/supervisor-cli.js policy
  node dist/src/supervisor-cli.js scenarios

All responses are JSON. State commands accept --state-dir PATH
(default .runtime/supervisor-sim). Each state directory is one simulation domain.
Virtual time advances immediately; no hardware is queried or loaded.
There is no live/run command, policy override, model endpoint request, or patch apply.
Reset applies only to synthetic faults and never approves live execution or policy changes.
Exit: 0 success; 1 internal/storage error; 2 rejected/failed task; 3 fault; 4 busy.
`;
let store: Store | undefined;
try {
  const { values, positionals } = parseArgs({ allowPositionals: true, options: {
    task: { type: 'string' }, scenario: { type: 'string' }, 'state-dir': { type: 'string' },
    reason: { type: 'string' }, 'acknowledge-simulation': { type: 'boolean' }, help: { type: 'boolean' },
  } });
  const command = positionals[0];
  if (values.help || !command) console.log(help);
  else {
    const allowed: Record<string, string[]> = {
      plan: ['task'], simulate: ['task', 'scenario', 'state-dir'], status: ['state-dir'],
      'reset-fault': ['state-dir', 'reason', 'acknowledge-simulation'], policy: [], scenarios: [],
    };
    if (positionals.length !== 1 || !allowed[command])
      throw new Rejected('UNSUPPORTED_COMMAND', 'Expected plan, simulate, status, reset-fault, policy, or scenarios. Live execution is unavailable.');
    if (Object.keys(values).some(k => !allowed[command].includes(k)))
      throw new Rejected('INVALID_OPTION', 'Option is not supported by this command.');
    let output: unknown;
    if (command === 'plan' || command === 'simulate') {
      if (!values.task) throw new Rejected('TASK_REQUIRED', '--task JSON file is required.');
      const task = validateTask(readJson(values.task));
      if (command === 'plan') output = plan(task);
      else {
        const scenario = values.scenario ?? 'happy';
        if (!(SCENARIOS as readonly string[]).includes(scenario))
          throw new Rejected('INVALID_SCENARIO', 'Unknown scenario. Use scenarios to list synthetic fixtures.');
        store = new Store(values['state-dir'] ?? '.runtime/supervisor-sim'); store.acquire();
        const result = simulate(store, task, new Simulator(scenario as Scenario));
        output = result;
        process.exitCode = result.status === 'fault' ? 3 : result.status === 'succeeded' ? 0 : 2;
      }
    } else if (command === 'policy') output = { version: 1, mode: 'simulation', policyHash: POLICY_HASH, policy: POLICY,
      changes: 'No runtime policy mutation is supported. Changes require a separately reviewed implementation; fault reset cannot approve them.' };
    else if (command === 'scenarios') output = { version: 1, mode: 'simulation', scenarios: SCENARIOS };
    else {
      store = new Store(values['state-dir'] ?? '.runtime/supervisor-sim'); store.acquire();
      output = command === 'status' ? inspect(store) : resetFault(store, values.reason ?? '', !!values['acknowledge-simulation']);
      if (command === 'status' && (output as { state: string }).state === 'FAULT') process.exitCode = 3;
    }
    console.log(JSON.stringify(output));
  }
} catch (error) {
  const parseError = error instanceof Error && 'code' in error && String(error.code).startsWith('ERR_PARSE_ARGS_');
  const code = error instanceof Busy ? 'BUSY' : error instanceof Rejected ? error.code : parseError ? 'INVALID_OPTION' : 'INTERNAL_ERROR';
  const message = error instanceof Error ? error.message : 'Unknown error';
  console.error(JSON.stringify({ version: 1, mode: 'simulation', error: { code, message } }));
  process.exitCode = error instanceof Busy ? 4 : error instanceof Rejected || parseError ? 2 : 1;
} finally {
  try { store?.release(); }
  catch {
    console.error(JSON.stringify({ version: 1, mode: 'simulation', error: { code: 'LOCK_RELEASE_FAILED', message: 'Manual lock inspection required.' } }));
    process.exitCode = 1;
  }
}
