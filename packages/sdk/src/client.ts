import type { MissionRun } from '../../runtime/src/index';
import type {
  AgentOsHeartbeatControlState,
  AgentOsHeartbeatResult,
  AgentOsIntegrationHealthReport,
  AgentOsIntegrationReadiness,
  CreateMissionRunInput,
  DailyOpsRunInput,
  HeartbeatCronRequestInput,
  IntegrationHealthInput,
  ListMissionRunsInput,
  MissionControlSnapshot,
  MissionRunGateInput,
} from './contracts';
import type { ActionResult } from './result';

type FetchLike = typeof fetch;

export interface MissionControlClientOptions {
  baseUrl: string;
  fetch?: FetchLike;
  headers?: Record<string, string>;
}

export interface MissionControlClient {
  getSnapshot(input: { organizationId: string }): Promise<ActionResult<MissionControlSnapshot>>;
  listRuns(input: ListMissionRunsInput): Promise<ActionResult<MissionRun[]>>;
  createRun(input: CreateMissionRunInput): Promise<ActionResult<MissionRun>>;
  approveGate(input: MissionRunGateInput): Promise<ActionResult<MissionRun>>;
  rejectGate(input: MissionRunGateInput): Promise<ActionResult<MissionRun>>;
  createDailyOpsRun(input: DailyOpsRunInput): Promise<ActionResult<MissionRun>>;
  runHeartbeatCheck(): Promise<ActionResult<AgentOsHeartbeatResult>>;
  getHeartbeatControl(): Promise<ActionResult<AgentOsHeartbeatControlState>>;
  listReadiness(): Promise<ActionResult<AgentOsIntegrationReadiness[]>>;
  runIntegrationHealthCheck(input: IntegrationHealthInput): Promise<ActionResult<AgentOsIntegrationHealthReport>>;
  requestHeartbeatCronEnablement(input: HeartbeatCronRequestInput): Promise<ActionResult<MissionRun>>;
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '');
}

function buildUrl(baseUrl: string, path: string, query?: Record<string, string | number | undefined>) {
  const url = new URL(`${trimTrailingSlash(baseUrl)}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined) continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function readJson<T>(response: Response): Promise<T> {
  return response.json() as Promise<T>;
}

function createRequestInit(
  method: 'GET' | 'POST',
  body: unknown,
  headers?: Record<string, string>,
): RequestInit {
  if (method === 'GET') {
    return {
      method,
      headers,
    };
  }

  return {
    method,
    headers: {
      'content-type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(body ?? {}),
  };
}

export function createMissionControlClient(options: MissionControlClientOptions): MissionControlClient {
  const fetchImpl = options.fetch ?? fetch;

  async function request<T>(params: {
    path: string;
    method?: 'GET' | 'POST';
    query?: Record<string, string | number | undefined>;
    body?: unknown;
  }): Promise<ActionResult<T>> {
    const response = await fetchImpl(
      buildUrl(options.baseUrl, params.path, params.query),
      createRequestInit(params.method ?? 'GET', params.body, options.headers),
    );

    const data = await readJson<ActionResult<T>>(response);
    return data;
  }

  return {
    getSnapshot(input) {
      return request<MissionControlSnapshot>({
        path: '/snapshot',
        method: 'GET',
        query: {
          organizationId: input.organizationId,
        },
      });
    },
    listRuns(input) {
      return request<MissionRun[]>({
        path: '/runs',
        method: 'GET',
        query: {
          organizationId: input.organizationId,
          limit: input.limit,
        },
      });
    },
    createRun(input) {
      return request<MissionRun>({
        path: '/runs',
        method: 'POST',
        body: input,
      });
    },
    approveGate(input) {
      return request<MissionRun>({
        path: `/runs/${input.runId}/approve`,
        method: 'POST',
        body: input,
      });
    },
    rejectGate(input) {
      return request<MissionRun>({
        path: `/runs/${input.runId}/reject`,
        method: 'POST',
        body: input,
      });
    },
    createDailyOpsRun(input) {
      return request<MissionRun>({
        path: '/daily-ops',
        method: 'POST',
        body: input,
      });
    },
    runHeartbeatCheck() {
      return request<AgentOsHeartbeatResult>({
        path: '/heartbeat/check',
        method: 'POST',
      });
    },
    getHeartbeatControl() {
      return request<AgentOsHeartbeatControlState>({
        path: '/heartbeat/control',
        method: 'GET',
      });
    },
    listReadiness() {
      return request<AgentOsIntegrationReadiness[]>({
        path: '/readiness',
        method: 'GET',
      });
    },
    runIntegrationHealthCheck(input) {
      return request<AgentOsIntegrationHealthReport>({
        path: '/readiness/check',
        method: 'POST',
        body: input,
      });
    },
    requestHeartbeatCronEnablement(input) {
      return request<MissionRun>({
        path: '/heartbeat/cron-request',
        method: 'POST',
        body: input,
      });
    },
  };
}
