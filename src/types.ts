export type DiffSide = 'old' | 'new';

export interface SourceContext {
  file: string;
  text: string;
}

export interface ChangedLine extends SourceContext {
  side: DiffSide;
  line: number;
}

export interface ModelOptions {
  host?: string;
  model?: string;
}

export interface CopilotOptions extends ModelOptions {
  root: string;
}

export interface SuggestOptions extends CopilotOptions {
  file?: string;
  task?: string;
  line?: string | number;
}

export interface ReviewOptions extends CopilotOptions {
  staged?: boolean;
}

export interface Suggestion {
  file: string;
  line: number;
  explanation: string;
  code: string;
}

export interface Finding {
  file: string;
  line: number;
  side: DiffSide;
  severity: 'high' | 'medium' | 'low';
  title: string;
  explanation: string;
  suggestedFix: string;
}

export interface Review {
  summary: string;
  findings: Finding[];
  excluded: number;
  reviewedFiles: string[];
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface JsonSchema {
  type: 'string' | 'integer' | 'object' | 'array';
  additionalProperties?: boolean;
  required?: string[];
  properties?: Record<string, JsonSchema>;
  items?: JsonSchema;
  enum?: string[];
  minimum?: number;
}

export interface GenerateOptions extends ModelOptions {
  messages: ChatMessage[];
  schema: JsonSchema;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
