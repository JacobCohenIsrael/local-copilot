#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { realpath } from 'node:fs/promises';
import { suggest, review } from './copilot.js';
import { request, localEndpoint } from './model.js';
import { errorMessage, isRecord } from './types.js';
import type { Review, Suggestion } from './types.js';

type CommandResult =
  | { kind: 'doctor'; output: { host: string; models: string[]; message: string } }
  | { kind: 'suggest'; output: Suggestion }
  | { kind: 'review'; output: Review };

const help = `Local Copilot — local code suggestions and code review

  npm start -- doctor [--model NAME]
  npm start -- suggest --file PATH --task "what to write" [--line N] --model NAME
  npm start -- review [--staged] --model NAME

Options:
  --repo PATH   Repository directory (default: current directory)
  --host URL    Loopback Ollama origin (default: http://127.0.0.1:11434)
  --model NAME Installed local model; also LOCAL_COPILOT_MODEL
  --line N     Insert before this 1-based line (default: append)
  --staged     Review staged changes instead of unstaged tracked changes
  --keep-cache Keep the model loaded for 5 minutes after each response
  --json       Print machine-readable JSON
  --help       Show this help

Suggestions are printed for inspection. Files are never changed.
Review excludes untracked files; stage them to include them.
`;

// Strip terminal control characters from repository and model text.
const safe = (value: unknown): string => String(value).replace(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/g, '');
try {
  const { values, positionals } = parseArgs({ allowPositionals: true, options: {
    repo: { type: 'string' }, host: { type: 'string' }, model: { type: 'string' },
    file: { type: 'string' }, task: { type: 'string' }, line: { type: 'string' },
    staged: { type: 'boolean' }, json: { type: 'boolean' }, help: { type: 'boolean' },
    'keep-cache': { type: 'boolean' },
  } });
  const command = positionals[0];
  if (values.help || !command) console.log(help);
  else {
    if (positionals.length !== 1 || !['doctor', 'suggest', 'review'].includes(command)) throw new Error('Expected doctor, suggest, or review. Use --help.');
    const options = { ...values, keepCache: values['keep-cache'] ?? false, root: await realpath(values.repo || '.'), host: localEndpoint(values.host), model: values.model || process.env.LOCAL_COPILOT_MODEL };
    let result: CommandResult;
    if (command === 'doctor') {
      const data = await request(options.host, '/api/tags', undefined, 5000);
      if (!isRecord(data) || !Array.isArray(data.models) || !data.models.every(m => isRecord(m) && typeof m.name === 'string')) throw new Error('Ollama returned an invalid model list.');
      const models = data.models.map((m: { name: string }) => m.name);
      if (options.model && !models.some(m => m === options.model || m === `${options.model}:latest`)) throw new Error(`Model ${options.model} is not installed. Installed: ${models.join(', ') || '(none)'}`);
      result = { kind: 'doctor', output: { host: options.host, models, message: models.length ? 'Local model service is available.' : 'Ollama is running; install a local coding model.' } };
    } else if (command === 'suggest') result = { kind: 'suggest', output: await suggest(options) };
    else result = { kind: 'review', output: await review(options) };
    if (values.json) console.log(JSON.stringify(result.output, null, 2));
    else if (result.kind === 'doctor') {
      const { output } = result;
      console.log(safe(`${output.message}\nModels: ${output.models.join(', ') || '(none)'}`));
    } else if (result.kind === 'suggest') {
      const { output } = result;
      console.log(safe(`Insert before ${output.file}:${output.line}\n\n${output.explanation}\n\n${output.code}`));
    }
    else {
      const { output } = result;
      console.log(safe(output.summary));
      for (const f of output.findings) console.log(safe(`\n[${f.severity}] ${f.file}:${f.line} (${f.side}) — ${f.title}\n${f.explanation}\nSuggested fix: ${f.suggestedFix}`));
      console.log(`\n${output.findings.length} finding(s); ${output.reviewedFiles.length} file(s) reviewed; ${output.excluded} file(s) excluded.`);
    }
  }
} catch (error) {
  console.error(`Error: ${safe(errorMessage(error))}`);
  process.exitCode = 1;
}
