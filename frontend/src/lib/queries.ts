"use client";

/**
 * TanStack Query bindings for the Proofly API.
 *
 * Polling policy: a job is polled while it is still moving through the state
 * machine and stops the moment it reaches a terminal state. SSE carries the
 * narrative (`useResearchEvents`); polling carries the authoritative status and
 * counters, so the page stays correct even if the stream drops.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import {
  ApiError,
  ReportNotReadyError,
  askFollowUp,
  getEvidence,
  getReport,
  getResearchJob,
  getSources,
  startResearch,
} from "@/lib/api";
import {
  isReportReady,
  isTerminalStatus,
  type Evidence,
  type FollowUpAnswer,
  type Report,
  type ResearchJob,
  type ResearchSource,
  type StartResearchResponse,
} from "@/lib/types";

export const JOB_POLL_INTERVAL_MS = 2500;

export const queryKeys = {
  job: (id: string) => ["research", id] as const,
  report: (id: string) => ["research", id, "report"] as const,
  sources: (id: string) => ["research", id, "sources"] as const,
  evidence: (id: string, topic?: string) =>
    ["research", id, "evidence", topic ?? "__all__"] as const,
};

/** Never retry client errors — a 404 means "not found or not yours". */
function retryPolicy(failureCount: number, error: unknown): boolean {
  if (error instanceof ReportNotReadyError) return false;
  if (error instanceof ApiError) {
    if (error.isNetworkError) return failureCount < 2;
    if (error.status >= 400 && error.status < 500) return false;
  }
  return failureCount < 2;
}

export function useResearchJob(
  id: string | null | undefined,
  options: { enabled?: boolean } = {},
): UseQueryResult<ResearchJob, ApiError> {
  return useQuery<ResearchJob, ApiError>({
    queryKey: queryKeys.job(id ?? ""),
    queryFn: ({ signal }) => getResearchJob(id as string, signal),
    enabled: Boolean(id) && (options.enabled ?? true),
    retry: retryPolicy,
    refetchInterval: (query) =>
      isTerminalStatus(query.state.data?.status) ? false : JOB_POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
    staleTime: 0,
  });
}

export function useReport(
  id: string | null | undefined,
  options: { enabled?: boolean } = {},
): UseQueryResult<Report, ApiError> {
  return useQuery<Report, ApiError>({
    queryKey: queryKeys.report(id ?? ""),
    queryFn: ({ signal }) => getReport(id as string, signal),
    enabled: Boolean(id) && (options.enabled ?? true),
    retry: retryPolicy,
    // Reports are immutable once generated.
    staleTime: 5 * 60 * 1000,
  });
}

export function useSources(
  id: string | null | undefined,
  options: { enabled?: boolean } = {},
): UseQueryResult<ResearchSource[], ApiError> {
  return useQuery<ResearchSource[], ApiError>({
    queryKey: queryKeys.sources(id ?? ""),
    queryFn: ({ signal }) => getSources(id as string, signal),
    enabled: Boolean(id) && (options.enabled ?? true),
    retry: retryPolicy,
    staleTime: 60 * 1000,
  });
}

export function useEvidence(
  id: string | null | undefined,
  topic?: string,
  options: { enabled?: boolean } = {},
): UseQueryResult<Evidence[], ApiError> {
  return useQuery<Evidence[], ApiError>({
    queryKey: queryKeys.evidence(id ?? "", topic),
    queryFn: ({ signal }) => getEvidence(id as string, topic, signal),
    enabled: Boolean(id) && (options.enabled ?? true),
    retry: retryPolicy,
    staleTime: 60 * 1000,
  });
}

export function useStartResearch(): UseMutationResult<
  StartResearchResponse,
  ApiError,
  string
> {
  const queryClient = useQueryClient();
  return useMutation<StartResearchResponse, ApiError, string>({
    mutationFn: (productQuery: string) => startResearch(productQuery),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(data.researchJobId) });
    },
  });
}

/**
 * `POST /research/{id}/followup` — evidence-grounded Q&A over a finished job.
 * The backend answers only from evidence already gathered for this job.
 */
export function useFollowUp(
  id: string,
): UseMutationResult<FollowUpAnswer, ApiError, string> {
  return useMutation<FollowUpAnswer, ApiError, string>({
    mutationFn: (question: string) => askFollowUp(id, question),
  });
}

/** Convenience: is this job far enough along that a report exists? */
export function jobHasReport(job: ResearchJob | undefined): boolean {
  return isReportReady(job?.status);
}
