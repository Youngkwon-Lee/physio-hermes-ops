export const HEALTH_MEMORY_CONTEXT_SCHEMA_VERSION = 'health-memory-context.v1' as const;

export interface HealthMemoryContextItem {
  id: string;
  memoryType: string;
  memorySubtype: string | null;
  bodyRegion: string | null;
  title: string | null;
  summary: string | null;
  content: string;
  effectiveAt: string;
  occurredAt: string | null;
  occurredAtPrecision: 'exact' | 'date' | 'unknown';
  confirmationBasis: string | null;
}

export interface HealthMemoryContextPack {
  schemaVersion: typeof HEALTH_MEMORY_CONTEXT_SCHEMA_VERSION;
  items: HealthMemoryContextItem[];
}

export interface HealthMemoryKernelClientOptions {
  baseUrl: string;
  apiToken: string;
  serviceAccountId: string;
  organizationId: string;
  subjectPersonId: string;
  runtime: string;
  runtimeVersion?: string;
  fetch?: typeof fetch;
}

export interface HealthMemoryReadInput {
  subjectPersonId?: string;
  limit?: number;
  requestId?: string;
}

export class HealthMemoryKernelError extends Error {
  readonly status: number | null;
  readonly code: string | null;

  constructor(
    message: string,
    status: number | null,
    code: string | null,
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = 'HealthMemoryKernelError';
  }
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '');
}

function clampLimit(limit?: number) {
  if (!Number.isFinite(limit)) return 20;
  return Math.max(1, Math.min(Math.trunc(limit as number), 20));
}

function errorFromResponse(status: number, body: unknown) {
  const record = body && typeof body === 'object' ? (body as Record<string, unknown>) : {};
  const code = typeof record.code === 'string' ? record.code : null;
  // Never copy response bodies into an ops error: they may contain PHI or
  // repository details. The API already returns a stable machine code.
  return new HealthMemoryKernelError(`Health Memory API request failed (${status}).`, status, code);
}

export function createHealthMemoryKernelClient(options: HealthMemoryKernelClientOptions) {
  const fetchImpl = options.fetch ?? fetch;

  return {
    async readContext(input: HealthMemoryReadInput = {}): Promise<HealthMemoryContextPack> {
      const subjectPersonId = input.subjectPersonId ?? options.subjectPersonId;
      const response = await fetchImpl(`${trimTrailingSlash(options.baseUrl)}/api/kernel/v0`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-hermes-api-key': options.apiToken,
        },
        body: JSON.stringify({
          domain: 'memory',
          subjectPersonId,
          limit: clampLimit(input.limit),
          context: {
            serviceAccountId: options.serviceAccountId,
            organizationId: options.organizationId,
            scopes: ['memory:read'],
          },
          provenance: {
            runtime: options.runtime,
            runtimeVersion: options.runtimeVersion,
            requestId: input.requestId ?? globalThis.crypto.randomUUID(),
          },
        }),
      });

      let body: unknown;
      try {
        body = await response.json();
      } catch {
        throw new HealthMemoryKernelError('Health Memory API returned invalid JSON.', response.status, null);
      }

      if (!response.ok || !body || typeof body !== 'object' || (body as { success?: unknown }).success !== true) {
        throw errorFromResponse(response.status, body);
      }

      const data = (body as { data?: { context?: HealthMemoryContextPack } }).data?.context;
      if (!data || data.schemaVersion !== HEALTH_MEMORY_CONTEXT_SCHEMA_VERSION || !Array.isArray(data.items)) {
        throw new HealthMemoryKernelError('Health Memory API returned an invalid context contract.', response.status, 'INVALID_RESPONSE');
      }
      return data;
    },
  };
}
