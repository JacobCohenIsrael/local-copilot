import { ideSuggest } from './ide.js';
import { errorMessage } from './types.js';

try {
  const chunks: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of process.stdin) {
    const buffer = Buffer.from(chunk);
    bytes += buffer.length;
    if (bytes > 512 * 1024) throw new Error('IDE request exceeds 512 KiB.');
    chunks.push(buffer);
  }
  console.log(JSON.stringify(await ideSuggest(JSON.parse(Buffer.concat(chunks).toString('utf8')))));
} catch (error) {
  console.error(JSON.stringify({ error: errorMessage(error) }));
  process.exitCode = 1;
}
