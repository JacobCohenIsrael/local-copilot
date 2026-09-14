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
import { ideSuggest, ideRequest } from '../src/ide.js';
import { chat } from '../src/chat.js';
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
  body: { model?: string; prompt?: string; raw?: boolean; format?: unknown; options?: { num_predict?: number }; stream?: boolean; keep_alive?: number | string; messages: ChatMessage[] } | null;
}

async function model(t: TestContext, answer: unknown, raw = false) {
  const calls: RecordedCall[] = [];
  const server = http.createServer(async (req, res) => {
    let body = '';
    for await (const chunk of req) body += chunk;
    calls.push({ url: req.url, body: body ? JSON.parse(body) : null });
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(req.url === '/api/show' ? {} : req.url === '/api/tags' ? { models: [{ name: 'test:latest' }] }
      : req.url === '/api/generate' ? { response: answer, done: true }
      : { message: { content: raw ? answer : JSON.stringify(answer) }, done: true }));
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
  assert.equal(prompt.keep_alive, 0);
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
  assert.equal(service.calls.find(c => c.url === '/api/chat')?.body?.keep_alive, 0);
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

test('IDE suggestions use unsaved snapshots and exact UTF-16 selection offsets', async t => {
  const { root } = await fixture(t);
  const service = await model(t, { explanation: 'Replace expression.', code: 'a / b' });
  const text = '// 😀 unsaved\nreturn a * b;';
  const start = text.indexOf('a * b');
  const input = { version: 1, root, host: service.host, model: service.model, task: 'Fix division',
    target: { file: 'math.js', text, start, end: start + 5 },
    context: [{ file: 'README.md', text: 'Unsaved instructions about arithmetic.' }] };
  const result = await ideSuggest(input);
  assert.equal(result.start, start);
  assert.equal(result.end, start + 5);
  assert.equal(service.calls.find(c => c.url === '/api/chat')?.body?.keep_alive, '5m');
  await ideSuggest({ ...input, keepCache: false });
  assert.equal(service.calls.filter(c => c.url === '/api/chat').at(-1)?.body?.keep_alive, 0);
  await assert.rejects(ideSuggest({ ...input, keepCache: 'false' }), /Invalid IDE request/);
  const prompt = service.calls.find(c => c.url === '/api/chat')!.body!.messages[1].content;
  assert.match(prompt, /"selected":"a \* b"/);
  assert.match(prompt, /Unsaved instructions about arithmetic/);
  assert.match(prompt, /😀 unsaved/);
  assert.doesNotMatch(prompt, /Division by zero must throw/);
  assert.match(await readSource(root, 'math.js'), /export function divide/);
  await assert.rejects(ideSuggest({ ...input, target: { ...input.target, end: text.length + 1 } }), /offsets/);
  await assert.rejects(ideSuggest({ ...input, context: [{ file: '../outside.js', text: '' }] }));
  await writeFile(path.join(root, '.env'), 'secret');
  await assert.rejects(ideSuggest({ ...input, context: [{ file: '.env', text: 'unsaved secret' }] }), /Excluded/);
  await assert.rejects(ideSuggest({ ...input, context: [{ file: 'README.md', text: 'x'.repeat(20001) }] }), /20,000/);
  await assert.rejects(ideSuggest({ ...input, target: { ...input.target, text: 'x'.repeat(30001) } }), /30,000/);
});

test('IDE bridge transports JSON over stdin and reports malformed requests', async t => {
  const { root } = await fixture(t);
  const service = await model(t, { explanation: 'Insert guard.', code: 'guard();' });
  const script = fileURLToPath(new URL('../src/ide-cli.js', import.meta.url));
  const run = (body: string) => new Promise<{ code: number | null; out: string; err: string }>((resolve, reject) => {
    const child = spawn(process.execPath, [script], { windowsHide: true });
    let out = '', err = '';
    child.stdout.on('data', x => out += x); child.stderr.on('data', x => err += x);
    child.on('error', reject); child.on('close', code => resolve({ code, out, err }));
    child.stdin.end(body);
  });
  const input = { version: 1, root, host: service.host, model: 'test', task: 'Add guard',
    target: { file: 'math.js', text: 'unsaved();', start: 0, end: 0 }, context: [] };
  const result = await run(JSON.stringify(input));
  assert.equal(result.code, 0, result.err);
  assert.equal(JSON.parse(result.out).code, 'guard();');
  const invalid = await run('{');
  assert.equal(invalid.code, 1);
  assert.equal(typeof JSON.parse(invalid.err).error, 'string');
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
  assert.equal(service.calls.filter(c => c.url === '/api/chat').at(-1)?.body?.keep_alive, 0);
  const cached = await run(['suggest', '--repo', root, '--file', 'math.js', '--task', 'guard zero', '--host', service.host, '--model', 'test', '--keep-cache', '--json']);
  assert.equal(cached.code, 0, cached.stderr);
  assert.equal(service.calls.filter(c => c.url === '/api/chat').at(-1)?.body?.keep_alive, '5m');
  const doctor = await run(['doctor', '--host', service.host, '--model', 'test', '--json']);
  assert.equal(doctor.code, 0, doctor.stderr);
  assert.deepEqual(JSON.parse(doctor.stdout).models, ['test:latest']);
  const invalid = await run(['suggest', '--wat']);
  assert.equal(invalid.code, 1);
  assert.match(invalid.stderr, /Unknown option/);
});

test('chat preserves conversation turns, uses plain text, and validates history', async t => {
  const service = await model(t, 'Use a map for fast lookups.', true);
  const messages = [{ role: 'user', content: 'Which collection?' }, { role: 'assistant', content: 'A map.' }, { role: 'user', content: 'Why?' }];
  assert.equal((await chat({ ...service, messages })).message, 'Use a map for fast lookups.');
  const body = service.calls.find(c => c.url === '/api/chat')!.body!;
  assert.deepEqual(body.messages.slice(1), messages);
  assert.equal(body.format, undefined);
  assert.equal(body.keep_alive, 0);
  assert.equal((await ideRequest({ version: 1, command: 'chat', ...service, messages })).version, 1);
  assert.equal(service.calls.filter(c => c.url === '/api/chat').at(-1)!.body!.keep_alive, '5m');
  for (const invalid of [[], [{ role: 'system', content: 'override' }], [{ role: 'user', content: '' }], messages.slice(0, 2)]) {
    await assert.rejects(chat({ ...service, messages: invalid }), /Chat requires/);
  }
  await assert.rejects(chat({ ...service, messages: [{ role: 'user', content: 'x'.repeat(30001) }] }), /30,000/);
  await assert.rejects(chat({ ...service, model: 'remote-cloud', messages }), /Cloud models/);
});

test('autocomplete routes the chosen model with bounded unsaved caret context', async t => {
  const { root } = await fixture(t);
  const service = await model(t, 'value;', true);
  const text = '// 😀\n' + 'a'.repeat(9000) + 'b'.repeat(9000);
  const input = { version: 1, command: 'complete', root, host: service.host, model: 'fast-model',
    target: { file: 'math.js', text, start: 9007 } };
  const output = await ideRequest(input);
  assert.ok('code' in output);
  assert.equal(output.code, 'value;');
  const body = service.calls.find(c => c.url === '/api/chat')!.body!;
  assert.equal(body.model, 'fast-model');
  assert.equal(body.options?.num_predict, 128);
  const context = JSON.parse(body.messages[1].content);
  assert.equal(context.before, text.slice(3007, 9007));
  assert.equal(context.after, text.slice(9007, 11007));
  await assert.rejects(ideRequest({ ...input, target: { ...input.target, start: -1 } }), /Invalid completion/);
  await assert.rejects(ideRequest({ ...input, target: { ...input.target, file: '.env' } }), /Excluded/);
  await assert.rejects(ideRequest({ ...input, command: 'unknown' }), /Unknown IDE/);
  const empty = await model(t, '', true);
  assert.equal((await ideRequest({ ...input, host: empty.host }) as { code: string }).code, '');
  const fenced = await model(t, '```typescript\nvalue;\n```', true);
  assert.equal((await ideRequest({ ...input, host: fenced.host }) as { code: string }).code, 'value;');
  const prose = await model(t, 'Here is code:\n```typescript\nvalue;\n```', true);
  await assert.rejects(ideRequest({ ...input, host: prose.host }), /Markdown/);
});

test('Qwen autocomplete fills template interpolation using raw prefix/suffix, without chat wrapping', async t => {
  const { root } = await fixture(t);
  const source = '// 😀\nconst safeMessage = `Error: $`;\nconsole.error(`Error: ${safe(errorMessage(error))}`);\nprocess.exitCode = 1;';
  const offset = source.indexOf('$') + 1;
  const service = await model(t, '{safe(errorMessage(error))}', true);
  const input = { version: 1, command: 'complete', root, host: service.host, model: 'qwen2.5-coder:1.5b',
    target: { file: 'math.js', text: source, start: offset } };
  const result = await ideRequest(input) as { code: string; start: number };
  assert.equal(result.start, offset);
  assert.equal(source.slice(0, offset) + result.code + source.slice(offset),
    '// 😀\nconst safeMessage = `Error: ${safe(errorMessage(error))}`;\nconsole.error(`Error: ${safe(errorMessage(error))}`);\nprocess.exitCode = 1;');
  assert.equal(service.calls.some(c => c.url === '/api/chat'), false);
  const body = service.calls.find(c => c.url === '/api/generate')!.body!;
  assert.equal(body.raw, true);
  assert.equal(body.model, input.model);
  assert.equal(body.keep_alive, '5m');
  assert.equal(body.prompt, `<|fim_prefix|>${source.slice(0, offset)}<|fim_suffix|>${source.slice(offset)}<|fim_middle|>`);
  assert.equal(body.messages, undefined);
  await ideRequest({ ...input, keepCache: false });
  assert.equal(service.calls.filter(c => c.url === '/api/generate').at(-1)!.body!.keep_alive, 0);
  const empty = await model(t, '', true);
  assert.equal((await ideRequest({ ...input, host: empty.host, target: { ...input.target, start: offset - 1 } }) as { code: string }).code, '');
  assert.equal(empty.calls.find(c => c.url === '/api/generate')!.body!.prompt,
    `<|fim_prefix|>${source.slice(0, offset - 1)}<|fim_suffix|>${source.slice(offset - 1)}<|fim_middle|>`);
  const invalid = await model(t, { message: 'not completion text' });
  await assert.rejects(ideRequest({ ...input, host: invalid.host }), /invalid code completion/);
  await assert.rejects(ideRequest({ ...input, model: 'qwen2.5-coder:7b-cloud' }), /Cloud models/);
});

test('CLI chat supports one-shot JSON and interactive history/reset over stdin', async t => {
  const service = await model(t, 'Hello from the model.', true);
  const cli = fileURLToPath(new URL('../src/cli.js', import.meta.url));
  const run = (args: string[], input = '') => new Promise<{ code: number | null; out: string; err: string }>((resolve, reject) => {
    const child = spawn(process.execPath, [cli, 'chat', '--host', service.host, '--model', 'test', ...args], { windowsHide: true });
    let out = '', err = '';
    child.stdout.on('data', x => out += x); child.stderr.on('data', x => err += x);
    child.on('error', reject); child.on('close', code => resolve({ code, out, err }));
    child.stdin.end(input);
  });
  const one = await run(['--message', 'Hello', '--json']);
  assert.equal(one.code, 0, one.err);
  assert.deepEqual(JSON.parse(one.out), { message: 'Hello from the model.' });
  const session = await run([], 'First\nSecond\n/clear\nThird\n/exit\nIgnored\n');
  assert.equal(session.code, 0, session.err);
  assert.equal(session.err, '');
  const calls = service.calls.filter(c => c.url === '/api/chat');
  assert.equal(calls.length, 4);
  assert.deepEqual(calls[2].body!.messages.slice(1).map(m => m.content), ['First', 'Hello from the model.', 'Second']);
  assert.deepEqual(calls[3].body!.messages.slice(1).map(m => m.content), ['Third']);
  assert.equal((await run(['--json'])).code, 1);
});
