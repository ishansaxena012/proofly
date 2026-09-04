"use client";

/**
 * Live subscription to `GET /api/v1/research/{id}/events`.
 *
 * The backend replays every persisted `research_events` row before streaming
 * live, so a refresh or a late subscriber still sees the full history. That
 * also means reconnects re-deliver history, so events are de-duplicated on a
 * stable key.
 *
 * Transport: `EventSource` first (the documented client), with the bearer
 * credential passed as a query parameter because `EventSource` cannot set
 * headers. If the stream never opens — e.g. the backend only accepts the
 * `Authorization` header — it falls back to a fetch + ReadableStream reader
 * that can send real headers. Both transports feed the same event list.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE_URL, researchEventsUrl } from "@/lib/api";
import { getCurrentAccessToken } from "@/lib/auth/session";
import { RESEARCH_EVENT_TYPES, type ResearchEvent, type ResearchEventData } from "@/lib/types";

export type EventStreamStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed" | "error";

export interface UseResearchEventsResult {
  events: ResearchEvent[];
  status: EventStreamStatus;
  /** Non-fatal: polling still drives the page when the stream is unavailable. */
  error: string | null;
  transport: "eventsource" | "fetch" | null;
}

/** EventSource failures before we give up on it and try the fetch transport. */
const MAX_EVENTSOURCE_FAILURES = 2;

function eventKey(eventType: string, data: ResearchEventData): string {
  return `${eventType}::${data.createdAt ?? ""}::${data.message ?? ""}`;
}

function parseEventData(raw: string): ResearchEventData | null {
  try {
    const parsed = JSON.parse(raw) as Partial<ResearchEventData>;
    return {
      message: typeof parsed.message === "string" ? parsed.message : null,
      payload:
        parsed.payload && typeof parsed.payload === "object"
          ? (parsed.payload as Record<string, unknown>)
          : null,
      createdAt:
        typeof parsed.createdAt === "string" ? parsed.createdAt : new Date().toISOString(),
    };
  } catch {
    // A non-JSON frame is still worth showing rather than silently dropping.
    if (!raw.trim()) return null;
    return { message: raw, payload: null, createdAt: new Date().toISOString() };
  }
}

export function useResearchEvents(
  researchJobId: string | null | undefined,
  options: { enabled?: boolean } = {},
): UseResearchEventsResult {
  const enabled = (options.enabled ?? true) && Boolean(researchJobId);

  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [status, setStatus] = useState<EventStreamStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [transport, setTransport] = useState<"eventsource" | "fetch" | null>(null);

  const seenKeys = useRef<Set<string>>(new Set());

  const push = useCallback((eventType: string, data: ResearchEventData) => {
    const key = eventKey(eventType, data);
    if (seenKeys.current.has(key)) return;
    seenKeys.current.add(key);
    setEvents((previous) =>
      [...previous, { ...data, eventType, key }].sort((a, b) => {
        const at = Date.parse(a.createdAt);
        const bt = Date.parse(b.createdAt);
        if (Number.isNaN(at) || Number.isNaN(bt) || at === bt) return 0;
        return at - bt;
      }),
    );
  }, []);

  useEffect(() => {
    if (!enabled || !researchJobId) {
      setStatus("idle");
      return;
    }

    // A fresh job id means a fresh history.
    seenKeys.current = new Set();
    setEvents([]);
    setError(null);
    setStatus("connecting");

    let disposed = false;
    let source: EventSource | null = null;
    let abort: AbortController | null = null;
    let failures = 0;

    const token = getCurrentAccessToken();

    /* ── Transport 2: fetch + ReadableStream (can send real headers) ─────── */
    const startFetchTransport = async () => {
      if (disposed) return;
      setTransport("fetch");
      setStatus((s) => (s === "open" ? "reconnecting" : "connecting"));
      abort = new AbortController();

      try {
        const response = await fetch(
          `${API_BASE_URL}/research/${encodeURIComponent(researchJobId)}/events`,
          {
            headers: {
              Accept: "text/event-stream",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            signal: abort.signal,
            cache: "no-store",
          },
        );

        if (!response.ok || !response.body) {
          throw new Error(`Event stream responded with ${response.status}.`);
        }

        if (disposed) return;
        setStatus("open");
        setError(null);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done || disposed) break;
          buffer += decoder.decode(value, { stream: true });

          let boundary = buffer.search(/\r?\n\r?\n/);
          while (boundary !== -1) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + (buffer[boundary] === "\r" ? 4 : 2));
            let frameEvent = "message";
            const dataLines: string[] = [];
            for (const line of frame.split(/\r?\n/)) {
              if (line.startsWith(":")) continue;
              if (line.startsWith("event:")) frameEvent = line.slice(6).trim();
              else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
            }
            if (dataLines.length > 0) {
              const parsedData = parseEventData(dataLines.join("\n"));
              if (parsedData) push(frameEvent, parsedData);
            }
            boundary = buffer.search(/\r?\n\r?\n/);
          }
        }

        if (!disposed) setStatus("closed");
      } catch (cause) {
        if (disposed || abort?.signal.aborted) return;
        setStatus("error");
        setError(
          cause instanceof Error
            ? `Live event stream unavailable (${cause.message}) — falling back to polling.`
            : "Live event stream unavailable — falling back to polling.",
        );
      }
    };

    /* ── Transport 1: EventSource ────────────────────────────────────────── */
    const startEventSource = () => {
      if (disposed) return;
      setTransport("eventsource");
      try {
        source = new EventSource(researchEventsUrl(researchJobId, token));
      } catch {
        void startFetchTransport();
        return;
      }

      const handle = (eventType: string) => (raw: MessageEvent<string>) => {
        failures = 0;
        setStatus("open");
        setError(null);
        const parsedData = parseEventData(raw.data);
        if (parsedData) push(eventType, parsedData);
      };

      source.onopen = () => {
        failures = 0;
        setStatus("open");
        setError(null);
      };

      // Named frames: one listener per documented event type.
      for (const type of RESEARCH_EVENT_TYPES) {
        source.addEventListener(type, handle(type) as EventListener);
      }
      // Unnamed frames (heartbeats or a backend that omits `event:`).
      source.onmessage = handle("message") as unknown as (e: MessageEvent) => void;

      source.onerror = () => {
        if (disposed) return;
        failures += 1;
        if (failures > MAX_EVENTSOURCE_FAILURES) {
          source?.close();
          source = null;
          void startFetchTransport();
          return;
        }
        setStatus("reconnecting");
      };
    };

    if (typeof window !== "undefined" && "EventSource" in window) {
      startEventSource();
    } else {
      void startFetchTransport();
    }

    return () => {
      disposed = true;
      source?.close();
      abort?.abort();
    };
  }, [enabled, researchJobId, push]);

  return useMemo(
    () => ({ events, status, error, transport }),
    [events, status, error, transport],
  );
}
