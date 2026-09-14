import test from 'node:test';
import type { TestContext } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, mkdir, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { execFileSync, spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { suggest, review } from '../src/copilot.js';
import { readSource, relatedContext, diffLocations } from '../src/context.js';
import { localEndpoint } from '../src/model.js';
import type { ChatMessage } from '../src/types.js';

async function fixture(t: TestContext) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'local-copilot-'));
  t.after(() => {
    const relative = path.relative(os.tmpdir(), root);
    assert.ok(relative.startsWith('local-copilot-') && !relative.includes(path.sep));
    return rm(root, { recursive: true, force: true });
  });
  const git = (...args: string[]) => execFileSync('git', ['-C', root, ...args], { windowsHide: true });
  git('init', '-q');
  git('config', 'core.autocrlf', 'false');
  await writeFile(path.join(root, 'math.js'), 'export function divide(a, b) {\n  return a / b;\n}\n');
  await writeFile(path.join(root, 'README.md'), 'Math utilities. Division by zero must throw.');
  await writeFile(path.join(root, '.gitignore'), 'ignored.js\n');
  git('add', '.');
  git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'initial');
  return { root, git };
}

interface RecordedCall {
  url: string | undefined;
  body: { stream?: boolean; messages: ChatMessage[] } | null;
}

async function model(t: TestContext, answer: unknown) {
  const calls: RecordedCall[] = [];
  const server = http.createServer(async (req, res) => {
    let body = '';
    for await (const chunk of req) body += chunk;
    calls.push({ url: req.url, body: body ? JSON.parse(body) : null });
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(req.url === '/api/show' ? {} : req.url === '/api/tags' ? { models: [{ name: 'test:latest' }] } : { message: { content: JSON.stringify(answer) }, done: true }));
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise<void>((resolve, reject) => {
    server.closeAllConnections();
    server.close(error => error ? reject(error) : resolve());
  }));
  const address = server.address();
  assert.ok(address && typeof address !== 'string');
  return { host: `http://127.0.0.1:${address.port}`, model: 'test', calls };
}

test('suggest sends cursor split and project context without modifying the file', async t => {
  const { root } = await fixture(t);
  const service = await model(t, { explanation: 'Guard zero.', code: '  if (b === 0) throw new Error("division by zero");' });
  const before = await readSource(root, 'math.js');
  const output = await suggest({ root, ...service, file: 'math.js', task: 'Guard division by zero', line: '2' });
  assert.match(output.code, /b === 0/);
  assert.equal(output.line, 2);
  assert.equal(await readSource(root, 'math.js'), before);
  const prompt = service.calls.find(c => c.url === '/api/chat')?.body;
  assert.ok(prompt);
  assert.equal(prompt.stream, false);
  assert.match(prompt.messages[1].content, /Division by zero must throw/);
  assert.match(prompt.messages[1].content, /"before":"export function divide/);
  await assert.rejects(suggest({ root, ...service, file: 'math.js', task: 'x', line: 0 }), /--line/);
});

test('reviews unstaged and staged changes and rejects invented locations', async t => {
  const { root, git } = await fixture(t);
  await writeFile(path.join(root, 'math.js'), 'export function divide(a, b) {\n  return a * b;\n}\n');
  const finding = { file: 'math.js', line: 2, side: 'new', severity: 'high', title: 'Multiplication replaces division', explanation: 'divide(6, 2) returns 12 instead of 3.', suggestedFix: 'Return a / b.' };
  const service = await model(t, { summary: 'Arithmetic regression.', findings: [finding] });
  const output = await review({ root, ...service });
  assert.deepEqual(output.findings, [finding]);
  assert.deepEqual(output.reviewedFiles, ['math.js']);
  git('add', 'math.js');
  assert.equal((await review({ root, ...service })).findings.length, 0);
  assert.equal((await review({ root, ...service, staged: true })).findings.length, 1);
  const bad = await model(t, { summary: 'Bad location', findings: [{ ...finding, line: 99 }] });
  await assert.rejects(review({ root, ...bad, staged: true }), /outside the diff/);
  const nearby = await model(t, { summary: 'Wrong unchanged line', findings: [{ ...finding, line: 3 }] });
  await assert.rejects(review({ root, ...nearby, staged: true }), /outside the diff/);
});

test('context respects ignored files and excludes credentials and path traversal', async t => {
  const { root } = await fixture(t);
  await writeFile(path.join(root, '.env'), 'SECRET=do-not-send');
  await writeFile(path.join(root, 'ignored.js'), 'do-not-send');
  await mkdir(path.join(root, 'nested'));
  await writeFile(path.join(root, 'nested', 'binary.bin'), Buffer.from([0, 1, 2]));
  const context = await relatedContext(root, 'math.js');
  assert.ok(context.some(c => c.file === 'README.md'));
  assert.ok(!context.some(c => ['.env', 'ignored.js', 'nested/binary.bin'].includes(c.file)));
  await assert.rejects(readSource(root, '.env'), /Excluded/);
  await assert.rejects(readSource(root, '..'), /inside the repository/);
  assert.throws(() => localEndpoint('https://example.com'), /loopback/);
  assert.throws(() => localEndpoint('http://localhost:11434/path'), /loopback/);
});

test('deleted lines use old-side locations', () => {
  const locations = diffLocations('diff --git a/a.js b/a.js\n--- a/a.js\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-first\n-second\n');
  assert.deepEqual([...(locations.get('a.js:old') ?? [])], [1, 2]);
  assert.equal(locations.has('/dev/null:new'), false);
});

test('CLI works end to end against a local API and reports errors', async t => {
  const { root } = await fixture(t);
  const service = await model(t, { explanation: 'Add a guard.', code: '  if (!b) throw new Error("zero");' });
  const cli = fileURLToPath(new URL('../src/cli.js', import.meta.url));
  const run = (args: string[]) => new Promise<{ code: number | null; stdout: string; stderr: string }>((resolve, reject) => {
    const child = spawn(process.execPath, [cli, ...args], { windowsHide: true });
    let stdout = '', stderr = '';
    child.stdout.on('data', x => stdout += x);
    child.stderr.on('data', x => stderr += x);
    child.on('error', reject);
    child.on('close', code => resolve({ code, stdout, stderr }));
  });
  const result = await run(['suggest', '--repo', root, '--file', 'math.js', '--task', 'guard zero', '--line', '2', '--host', service.host, '--model', 'test', '--json']);
  assert.equal(result.code, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).line, 2);
  const doctor = await run(['doctor', '--host', service.host, '--model', 'test', '--json']);
  assert.equal(doctor.code, 0, doctor.stderr);
  assert.deepEqual(JSON.parse(doctor.stdout).models, ['test:latest']);
  const invalid = await run(['suggest', '--wat']);
  assert.equal(invalid.code, 1);
  assert.match(invalid.stderr, /Unknown option/);
});
