import { realpath, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { errorMessage, isRecord } from './types.js';
import type { ChangedLine, DiffSide, SourceContext } from './types.js';

export function git(root: string, args: string[]): string {
  try {
    return execFileSync('git', ['-c', 'core.quotePath=false', '-C', root, ...args], { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, windowsHide: true });
  } catch (error) {
    const stderr = isRecord(error) && error.stderr != null ? String(error.stderr).trim() : '';
    throw new Error(`Git failed: ${stderr || errorMessage(error)}`);
  }
}

export function isSensitive(file: string): boolean {
  return /(^|[/\\])(\.env(?:\..*)?|\.git|node_modules|vendor|dist|build|coverage|\.runtime)([/\\]|$)/i.test(file)
    || /\.(pem|key|p12|pfx)$/i.test(file)
    || /(^|[/\\])(credentials[^/\\]*|id_rsa|id_ed25519)$/i.test(file);
}

export async function readSource(root: string, file: string): Promise<string> {
  if (isSensitive(file)) throw new Error(`Excluded file: ${file}`);
  const base = await realpath(root);
  const target = await realpath(path.resolve(base, file));
  const relative = path.relative(base, target);
  if (relative.startsWith('..' + path.sep) || relative === '..' || path.isAbsolute(relative)) throw new Error('File must be inside the repository.');
  if (isSensitive(relative)) throw new Error(`Excluded file: ${file}`);
  const info = await stat(target);
  if (!info.isFile() || info.size > 128 * 1024) throw new Error(`File is not a text file under 128 KiB: ${file}`);
  const text = await readFile(target, 'utf8');
  if (text.includes('\0')) throw new Error(`Binary file excluded: ${file}`);
  return text;
}

export async function relatedContext(root: string, focus: string, budget = 10000): Promise<SourceContext[]> {
  let files: string[];
  try { files = git(root, ['ls-files', '-z', '--cached', '--others', '--exclude-standard']).split('\0').filter(Boolean); }
  catch { return []; }
  const normalized = focus.replaceAll('\\', '/');
  const tokens = path.basename(normalized).split(/[^a-zA-Z0-9]+/).filter(t => t.length > 2);
  const score = (f: string) => (path.posix.dirname(f) === path.posix.dirname(normalized) ? 5 : 0)
    + tokens.filter(t => f.includes(t)).length * 2 + (/^(README.md|package.json|pyproject.toml|Cargo.toml)$/.test(f) ? 4 : 0);
  files = [...new Set(files)].filter(f => f !== normalized && !isSensitive(f)).sort((a, b) => score(b) - score(a) || a.localeCompare(b));
  const result: SourceContext[] = [];
  for (const file of files.slice(0, 40)) {
    if (budget <= 0 || result.length >= 6) break;
    try {
      const text = await readSource(root, file);
      if (text.length > budget) continue;
      result.push({ file, text });
      budget -= text.length;
    } catch { /* Ignore unavailable, binary, oversized, and excluded context. */ }
  }
  return result;
}

export function reviewDiff(root: string, staged = false): { diff: string; files: string[]; excluded: number } {
  const args = staged ? ['--cached'] : [];
  const names = git(root, ['diff', ...args, '--name-only', '-z']).split('\0').filter(Boolean);
  const files = names.filter(f => !isSensitive(f));
  if (!files.length) return { diff: '', files: [], excluded: names.length };
  const diff = git(root, ['--literal-pathspecs', 'diff', ...args, '--no-ext-diff', '--no-textconv', '--no-color', '--unified=4', '--', ...files]);
  if (diff.length > 48000) throw new Error('Diff exceeds 48,000 characters. Stage a smaller set of changes and use --staged.');
  return { diff, files, excluded: names.length - files.length };
}

// Provide explicit source line numbers so the model need not count diff lines.
export function diffLines(diff: string): ChangedLine[] {
  const result: ChangedLine[] = [];
  let oldFile: string | undefined, newFile: string | undefined;
  let oldLine = 0, newLine = 0, inHunk = false;
  const decode = (value: string): string => {
    const decoded: unknown = value.startsWith('"') ? JSON.parse(value) : value;
    if (typeof decoded !== 'string') throw new Error('Invalid file path in Git diff.');
    return decoded;
  };
  const add = (file: string | undefined, side: DiffSide, line: number, text: string) => {
    if (!file || file === '/dev/null') return;
    result.push({ file, side, line, text });
  };
  for (const line of diff.split('\n')) {
    if (line.startsWith('diff --git ')) { inHunk = false; oldFile = newFile = undefined; }
    else if (!inHunk && line.startsWith('--- ')) oldFile = decode(line.slice(4)).replace(/^a\//, '');
    else if (!inHunk && line.startsWith('+++ ')) newFile = decode(line.slice(4)).replace(/^b\//, '');
    else if (line.startsWith('@@ ')) {
      const match = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
      if (match) { oldLine = Number(match[1]); newLine = Number(match[2]); inHunk = true; }
    } else if (inHunk && line.startsWith('+')) add(newFile, 'new', newLine++, line.slice(1));
    else if (inHunk && line.startsWith('-')) add(oldFile, 'old', oldLine++, line.slice(1));
    else if (inHunk && line.startsWith(' ')) { oldLine++; newLine++; }
  }
  return result;
}

export function diffLocations(diff: string): Map<string, Set<number>> {
  const result = new Map<string, Set<number>>();
  for (const { file, side, line } of diffLines(diff)) {
    const key = `${file}:${side}`;
    const lines = result.get(key) ?? new Set<number>();
    lines.add(line);
    result.set(key, lines);
  }
  return result;
}
