/**
 * Session handling.
 *
 * Two modes, chosen at runtime from the public env vars:
 *
 *  1. **Supabase** — when both `NEXT_PUBLIC_SUPABASE_URL` and
 *     `NEXT_PUBLIC_SUPABASE_ANON_KEY` are set. Real auth via
 *     `@supabase/supabase-js`; the API bearer token is the Supabase-issued JWT,
 *     which the backend validates (`JWT_ISSUER_URI`).
 *
 *  2. **Dev stub** — when they are not. The browser holds a small local session
 *     record and sends `Authorization: Bearer dev-{userId}`, matching the
 *     backend's documented dev-auth fallback. The user id is derived
 *     deterministically (SHA-256 → RFC-4122 shaped uuid) from the email, so the
 *     same email always maps to the same `users.id` — no server round-trip and
 *     no invented identity. Ownership is still enforced server-side; this stub
 *     only decides which identity the browser claims.
 *
 * The dev stub is explicitly *not* authentication. It exists so the product is
 * usable end-to-end without Supabase credentials, and the UI says so.
 */

import { createClient } from "@supabase/supabase-js";
import type { Session as SupabaseSession, SupabaseClient } from "@supabase/supabase-js";

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const DEV_SESSION_STORAGE_KEY = "proofly.dev-session.v1";

export type AuthMode = "supabase" | "dev";

export interface ProoflySession {
  userId: string;
  email: string;
  displayName: string | null;
  /** Value used verbatim as the `Authorization: Bearer …` credential. */
  accessToken: string;
  mode: AuthMode;
}

export function isSupabaseConfigured(): boolean {
  return SUPABASE_URL.length > 0 && SUPABASE_ANON_KEY.length > 0;
}

export function authMode(): AuthMode {
  return isSupabaseConfigured() ? "supabase" : "dev";
}

/* ── Supabase client (lazy, browser-only singleton) ─────────────────────── */

let supabaseClient: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (!isSupabaseConfigured()) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.",
    );
  }
  if (!supabaseClient) {
    supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return supabaseClient;
}

export function sessionFromSupabase(session: SupabaseSession | null): ProoflySession | null {
  if (!session?.user || !session.access_token) return null;
  const meta = (session.user.user_metadata ?? {}) as Record<string, unknown>;
  const displayName =
    typeof meta.display_name === "string"
      ? meta.display_name
      : typeof meta.full_name === "string"
        ? meta.full_name
        : null;
  return {
    userId: session.user.id,
    email: session.user.email ?? "",
    displayName,
    accessToken: session.access_token,
    mode: "supabase",
  };
}

/* ── Dev stub ───────────────────────────────────────────────────────────── */

interface StoredDevSession {
  userId: string;
  email: string;
  displayName: string | null;
}

/**
 * Deterministic RFC-4122-shaped uuid derived from the email via SHA-256.
 * Deterministic so the identity survives cleared storage and other browsers.
 */
export async function deriveDevUserId(email: string): Promise<string> {
  const normalized = email.trim().toLowerCase();
  const data = new TextEncoder().encode(`proofly:dev-user:${normalized}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", data));
  const bytes = digest.slice(0, 16);
  // Version 4-shaped so downstream uuid parsers accept it.
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join("-");
}

export function devTokenFor(userId: string): string {
  return `dev-${userId}`;
}

export function readDevSession(): ProoflySession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(DEV_SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredDevSession>;
    if (!parsed.userId || !parsed.email) return null;
    return {
      userId: parsed.userId,
      email: parsed.email,
      displayName: parsed.displayName ?? null,
      accessToken: devTokenFor(parsed.userId),
      mode: "dev",
    };
  } catch {
    return null;
  }
}

export function writeDevSession(session: StoredDevSession): ProoflySession {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(DEV_SESSION_STORAGE_KEY, JSON.stringify(session));
  }
  return {
    ...session,
    accessToken: devTokenFor(session.userId),
    mode: "dev",
  };
}

export function clearDevSession(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(DEV_SESSION_STORAGE_KEY);
  }
}

export async function createDevSession(
  email: string,
  displayName?: string | null,
): Promise<ProoflySession> {
  const trimmed = email.trim().toLowerCase();
  const userId = await deriveDevUserId(trimmed);
  return writeDevSession({
    userId,
    email: trimmed,
    displayName: displayName?.trim() || null,
  });
}

/* ── Token access used by the API client ────────────────────────────────── */

/**
 * The current bearer credential, or null when signed out.
 * Registered by `AuthProvider` so `src/lib/api.ts` stays free of React state.
 */
let currentToken: string | null = null;

export function setCurrentAccessToken(token: string | null): void {
  currentToken = token;
}

export function getCurrentAccessToken(): string | null {
  if (currentToken) return currentToken;
  // Fallback for the dev stub before the provider has mounted (e.g. SSR-hydration race).
  if (!isSupabaseConfigured()) {
    return readDevSession()?.accessToken ?? null;
  }
  return null;
}
