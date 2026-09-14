import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { suggest, review } from '../src/copilot.js';

// This script runs from dist/scripts after compilation.
const project = fileURLToPath(new URL('../../', import.meta.url));
const runtime = path.join(project, '.runtime');
await mkdir(runtime, { recursive: true });
const root = await mkdtemp(path.join(runtime, 'demo-'));
const git = (...args: string[]) => execFileSync('git', ['-C', root, ...args], { windowsHide: true });
const original = 'export function divide(a, b) {\n  return a / b;\n}\n';
await writeFile(path.join(root, 'math.js'), original);
await writeFile(path.join(root, 'README.md'), 'Math utilities. divide(a, b) returns a divided by b. Division by zero must throw an Error.');
git('init', '-q');
git('config', 'core.autocrlf', 'false');
git('add', '.');
git('-c', 'user.name=Local Copilot Demo', '-c', 'user.email=demo@example.invalid', 'commit', '-qm', 'Demo baseline');
const options = { root, host: process.env.LOCAL_COPILOT_HOST || 'http://127.0.0.1:11435', model: process.env.LOCAL_COPILOT_MODEL || 'qwen2.5-coder:7b' };
const start = performance.now();
const suggestion = await suggest({ ...options, file: 'math.js', line: 2, task: 'Add a guard that throws an Error when b is zero.' });
const suggestionSeconds = (performance.now() - start) / 1000;
console.log(JSON.stringify({ suggestion, suggestionSeconds }, null, 2));
await writeFile(path.join(root, 'math.js'), original.replace('a / b', 'a * b'));
const reviewStart = performance.now();
const result = await review(options);
const reviewSeconds = (performance.now() - reviewStart) / 1000;
const evidence = { model: options.model, root, suggestion, suggestionSeconds, review: result, reviewSeconds };
await writeFile(path.join(root, 'results.json'), JSON.stringify(evidence, null, 2));
console.log(JSON.stringify({ review: result, reviewSeconds, evidence: path.join(root, 'results.json') }, null, 2));
if (!result.findings.some(f => f.file === 'math.js' && f.line === 2)) {
  console.error('Demo did not identify the known arithmetic regression. Inspect the output and try a stronger model.');
  process.exitCode = 1;
}
