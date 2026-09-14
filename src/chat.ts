import { generateText } from './model.js';
import { isRecord } from './types.js';
import type { ChatMessage, ModelOptions } from './types.js';

export async function chat(options: ModelOptions & { messages: unknown }): Promise<{ message: string }> {
  const messages = options.messages;
  if (!Array.isArray(messages) || !messages.length || messages.length > 40
    || !messages.every((m, i) => isRecord(m) && m.role === (i % 2 === 0 ? 'user' : 'assistant')
      && typeof m.content === 'string' && m.content.trim())
    || messages.length % 2 !== 1) throw new Error('Chat requires alternating user/assistant messages ending with a user message (maximum 40).');
  if (messages.reduce((n, m) => n + m.content.length, 0) > 30000) throw new Error('Chat exceeds 30,000 characters. Start a new conversation.');
  const message = await generateText({ ...options, messages: [
    { role: 'system', content: 'You are a helpful local coding assistant. Explain clearly. Do not claim to inspect files or run code or tests you have not been given.' },
    ...messages as ChatMessage[],
  ] });
  if (!message.trim()) throw new Error('Model returned an empty chat response.');
  return { message };
}
