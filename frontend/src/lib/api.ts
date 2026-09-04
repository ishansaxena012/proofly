/**
 * Typed client for the Proofly public API (`docs/API.md`).
 *
 * Every request carries `Authorization: Bearer {token}` — a Supabase JWT when
 * Supabase is configured, otherwise the documented `dev-{userId}` fallback.
 * Errors are normalised into `ApiError` so the UI can distinguish "backend
 * unreachable" from "404 / not yours" from a domain error code.
 */

import { getCurrentAccessToken } from "@/lib/auth/session";
import type {
  ApiErrorBody,
  ErrorCode,
  Evidence,
  FollowUpAnswer,
  Report,
  ResearchJob,
  ResearchJobStatus,
  ResearchSource,
  StartResearchResponse,
} from "@/lib/types";

const RAW_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080/api/v1";

/** Normalised base URL, no trailing slash. e.g. `http://localhost:8080/api/v1` */
export const API_BASE_URL = RAW_BASE_URL.replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: ErrorCode | string | null;
  readonly timestamp: string | null;
  /** True when the request never reached the backend (DNS/connection refused/CORS). */
  readonly isNetworkError: boolean;
  readonly body: unknown;

  constructor(init: {
    message: string;
    status: number;
    errorCode?: ErrorCode | string | null;
    timestamp?: string | null;
    isNetworkError?: boolean;
    body?: unknown;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.errorCode = init.errorCode ?? null;
    this.timestamp = init.timestamp ?? null;
    this.isNetworkError = init.isNetworkError ?? false;
    this.body = init.body ?? null;
  }

  get isUnauthorized(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

/** Thrown for the documented `409` from the report endpoint. */
export class ReportNotReadyError extends ApiError {
  readonly jobStatus: ResearchJobStatus | null;

  constructor(jobStatus: ResearchJobStatus | null) {
    super({
      message: jobStatus
        ? `The report is not available yet — this job is ${jobStatus}.`
        : "The report is not available yet.",
      status: 409,
      errorCode: "REPORT_NOT_READY",
    });
    this.name = "ReportNotReadyError";
    this.jobStatus = jobStatus;
  }
}

function buildUrl(path: string, query?: Record<string, string | undefined>): string {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function request<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    query?: Record<string, string | undefined>;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const { method = "GET", body, query, signal } = options;
  const token = getCurrentAccessToken();

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch (cause) {
    if (signal?.aborted) throw cause;
    throw new ApiError({
      message: `Could not reach the Proofly API at ${API_BASE_URL}. Is the backend running?`,
      status: 0,
      errorCode: "NETWORK_ERROR",
      isNetworkError: true,
    });
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!response.ok) {
    const errorBody = (parsed ?? {}) as Partial<ApiErrorBody> & {
      status?: ResearchJobStatus;
    };
    if (response.status === 409 && errorBody.status) {
      throw new ReportNotReadyError(errorBody.status);
    }
    throw new ApiError({
      message:
        errorBody.message ??
        (typeof parsed === "string" && parsed
          ? parsed
          : `Request failed with status ${response.status}.`),
      status: response.status,
      errorCode: errorBody.errorCode ?? null,
      timestamp: errorBody.timestamp ?? null,
      body: parsed,
    });
  }

  return parsed as T;
}

/* ── Endpoints ──────────────────────────────────────────────────────────── */

/** `POST /api/v1/research` */
export function startResearch(
  productQuery: string,
  signal?: AbortSignal,
): Promise<StartResearchResponse> {
  return request<StartResearchResponse>("/research", {
    method: "POST",
    body: { productQuery },
    signal,
  });
}

/** `GET /api/v1/research/{id}` */
export function getResearchJob(id: string, signal?: AbortSignal): Promise<ResearchJob> {
  return request<ResearchJob>(`/research/${encodeURIComponent(id)}`, { signal });
}

/** `GET /api/v1/research/{id}/report` — throws `ReportNotReadyError` on 409. */
export function getReport(id: string, signal?: AbortSignal): Promise<Report> {
  return request<Report>(`/research/${encodeURIComponent(id)}/report`, { signal });
}

/** `GET /api/v1/research/{id}/sources` */
export function getSources(id: string, signal?: AbortSignal): Promise<ResearchSource[]> {
  return request<ResearchSource[]>(`/research/${encodeURIComponent(id)}/sources`, {
    signal,
  });
}

/** `GET /api/v1/research/{id}/evidence?topic=` */
export function getEvidence(
  id: string,
  topic?: string,
  signal?: AbortSignal,
): Promise<Evidence[]> {
  return request<Evidence[]>(`/research/${encodeURIComponent(id)}/evidence`, {
    query: { topic },
    signal,
  });
}

/** `POST /api/v1/research/{id}/followup` */
export function askFollowUp(
  id: string,
  question: string,
  signal?: AbortSignal,
): Promise<FollowUpAnswer> {
  return request<FollowUpAnswer>(`/research/${encodeURIComponent(id)}/followup`, {
    method: "POST",
    body: { question },
    signal,
  });
}

/**
 * Absolute URL of the SSE stream for a job.
 *
 * `EventSource` cannot set request headers, so the bearer credential is also
 * appended as an `access_token` query parameter. The `Authorization` header is
 * still used by the fetch-based fallback transport in `useResearchEvents`.
 */
export function researchEventsUrl(id: string, token?: string | null): string {
  return buildUrl(`/research/${encodeURIComponent(id)}/events`, {
    access_token: token ?? undefined,
  });
}
