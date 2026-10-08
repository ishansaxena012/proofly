"use client";

import * as React from "react";

import {
  authMode,
  clearDevSession,
  createDevSession,
  getSupabaseClient,
  isSupabaseConfigured,
  readDevSession,
  sessionFromSupabase,
  setCurrentAccessToken,
  type AuthMode,
  type ProoflySession,
} from "@/lib/auth/session";

interface AuthContextValue {
  session: ProoflySession | null;
  /** True until the initial session lookup has settled. */
  loading: boolean;
  mode: AuthMode;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName?: string) => Promise<void>;
  /**
   * Redirects the browser to Google via Supabase OAuth. On success the browser
   * navigates away entirely, then back to `redirectPath` once Google/Supabase
   * finish; `AuthProvider`'s `onAuthStateChange` subscription picks up the
   * resulting session automatically on that page, so callers don't need a
   * dedicated callback route. Throws if Supabase isn't configured (Google
   * sign-in has no dev-stub equivalent — it needs a real Supabase project with
   * the Google provider enabled).
   */
  signInWithGoogle: (redirectPath: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const mode = authMode();
  const [session, setSession] = React.useState<ProoflySession | null>(null);
  const [loading, setLoading] = React.useState(true);

  const applySession = React.useCallback((next: ProoflySession | null) => {
    setCurrentAccessToken(next?.accessToken ?? null);
    setSession(next);
  }, []);

  React.useEffect(() => {
    let cancelled = false;

    if (!isSupabaseConfigured()) {
      applySession(readDevSession());
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    const supabase = getSupabaseClient();
    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (cancelled) return;
        applySession(sessionFromSupabase(data.session));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, next) => {
      if (cancelled) return;
      applySession(sessionFromSupabase(next));
    });

    return () => {
      cancelled = true;
      subscription.subscription.unsubscribe();
    };
  }, [applySession]);

  const signIn = React.useCallback(
    async (email: string, password: string) => {
      if (!isSupabaseConfigured()) {
        applySession(await createDevSession(email));
        return;
      }
      const supabase = getSupabaseClient();
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw new Error(error.message);
      applySession(sessionFromSupabase(data.session));
    },
    [applySession],
  );

  const signUp = React.useCallback(
    async (email: string, password: string, displayName?: string) => {
      if (!isSupabaseConfigured()) {
        applySession(await createDevSession(email, displayName));
        return;
      }
      const supabase = getSupabaseClient();
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: displayName ? { data: { display_name: displayName } } : undefined,
      });
      if (error) throw new Error(error.message);
      // With email confirmation on, `data.session` is null and the user must verify.
      applySession(sessionFromSupabase(data.session));
      if (!data.session) {
        throw new Error(
          "Account created. Check your inbox to confirm the address, then sign in.",
        );
      }
    },
    [applySession],
  );

  const signInWithGoogle = React.useCallback(async (redirectPath: string) => {
    if (!isSupabaseConfigured()) {
      throw new Error(
        "Google sign-in requires Supabase. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, and enable the Google provider in your Supabase project.",
      );
    }
    const supabase = getSupabaseClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}${redirectPath}` },
    });
    if (error) throw new Error(error.message);
    // `signInWithOAuth` navigates the browser to Google; there is no session to
    // apply yet on this page load.
  }, []);

  const signOut = React.useCallback(async () => {
    if (!isSupabaseConfigured()) {
      clearDevSession();
      applySession(null);
      return;
    }
    await getSupabaseClient().auth.signOut();
    applySession(null);
  }, [applySession]);

  const value = React.useMemo<AuthContextValue>(
    () => ({ session, loading, mode, signIn, signUp, signInWithGoogle, signOut }),
    [session, loading, mode, signIn, signUp, signInWithGoogle, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>.");
  return context;
}
