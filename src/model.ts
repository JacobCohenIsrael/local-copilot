import { errorMessage, isRecord } from './types.js';
import type { GenerateOptions } from './types.js';

export function localEndpoint(value = 'http://127.0.0.1:11434'): string {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('Model host must be a loopback HTTP(S) origin, such as http://127.0.0.1:11434.');
  }
  return url.origin;
}

export async function request(host: string | undefined, route: string, body?: unknown, timeout = 180000): Promise<unknown> {
  let response;
  try {
    response = await fetch(`${localEndpoint(host)}${route}`, {
      method: body ? 'POST' : 'GET', redirect: 'error', signal: AbortSignal.timeout(timeout),
      headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    throw new Error(`Cannot reach local model service: ${errorMessage(error)}. Start Ollama and run the doctor command.`);
  }
  if (!response.ok) throw new Error(`Ollama returned HTTP ${response.status}: ${(await response.text()).slice(0, 500)}`);
  return response.json();
}

export async function generate({ host, model, messages, schema, keepCache = false }: GenerateOptions): Promise<unknown> {
  if (!model || /(?:cloud|:latest-cloud)$/i.test(model)) throw new Error('Choose an installed local model with --model. Cloud models are unsupported.');
  const info = await request(host, '/api/show', { model });
  if (!isRecord(info)) throw new Error('Ollama returned invalid model information.');
  if (info.remote_host || info.remote_model) throw new Error('This model delegates to a remote service. Choose a local model.');
  // Retain for repeated requests only when requested; always expire after idle time.
  const result = await request(host, '/api/chat', { model, messages, stream: false, keep_alive: keepCache ? '5m' : 0, format: schema, options: { temperature: 0.1, num_ctx: 16384 } });
  if (isRecord(result) && result.done_reason === 'length') throw new Error('Model output was truncated; try a smaller request.');
  let output: unknown;
  try {
    if (!isRecord(result) || !isRecord(result.message) || typeof result.message.content !== 'string') throw new Error('Missing model content.');
    output = JSON.parse(result.message.content);
  }
  catch { throw new Error('Model returned invalid JSON. Try the request again or choose another local coding model.'); }
  return output;
}
