"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Info, Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const DEFAULT_REDIRECT = "/research";

/** Only allow in-app relative redirects. */
function safeRedirect(next: string | null): string {
  if (!next) return DEFAULT_REDIRECT;
  if (!next.startsWith("/") || next.startsWith("//")) return DEFAULT_REDIRECT;
  return next;
}

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session, loading, mode: authProviderMode, signIn, signUp } = useAuth();

  const isSignup = mode === "signup";
  const isDev = authProviderMode === "dev";
  const next = safeRedirect(searchParams.get("next"));

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!loading && session) router.replace(next);
  }, [loading, session, next, router]);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Enter your email address.");
      return;
    }
    if (!isDev && password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (isSignup) {
        await signUp(trimmedEmail, password, displayName || undefined);
      } else {
        await signIn(trimmedEmail, password);
      }
      router.replace(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container flex justify-center py-16 sm:py-24">
      <div className="w-full max-w-md space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="display text-3xl font-semibold">
            {isSignup ? "Create your account" : "Sign in"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {isSignup
              ? "Research jobs and reports are private to your account."
              : "Continue to your research jobs and reports."}
          </p>
        </div>

        {isDev ? (
          <Alert variant="info">
            <Info aria-hidden="true" />
            <AlertTitle>Development session</AlertTitle>
            <AlertDescription>
              Supabase credentials are not configured, so Proofly is using its documented
              dev-auth fallback: your email is mapped to a stable user id and requests are
              sent as{" "}
              <code className="font-mono text-xs">Authorization: Bearer dev-&#123;userId&#125;</code>
              . This identifies you, it does not authenticate you — the backend still
              enforces ownership on every job. Set{" "}
              <code className="font-mono text-xs">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
              <code className="font-mono text-xs">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> for
              real auth.
            </AlertDescription>
          </Alert>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>{isSignup ? "Sign up" : "Welcome back"}</CardTitle>
            <CardDescription>
              {isDev
                ? "Enter an email to open a local development session."
                : "Use your Proofly credentials."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4" noValidate>
              {isSignup ? (
                <div className="space-y-2">
                  <Label htmlFor="displayName">Display name (optional)</Label>
                  <Input
                    id="displayName"
                    name="displayName"
                    autoComplete="name"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Alex Chen"
                  />
                </div>
              ) : null}

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  aria-describedby={error ? "auth-error" : undefined}
                />
              </div>

              {!isDev ? (
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    required
                    autoComplete={isSignup ? "new-password" : "current-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 6 characters"
                  />
                </div>
              ) : null}

              {error ? (
                <p id="auth-error" role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              ) : null}

              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? (
                  <>
                    <Loader2 aria-hidden="true" className="animate-spin" />
                    {isSignup ? "Creating account…" : "Signing in…"}
                  </>
                ) : isSignup ? (
                  "Create account"
                ) : (
                  "Sign in"
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-muted-foreground">
          {isSignup ? (
            <>
              Already have an account?{" "}
              <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
                Sign in
              </Link>
            </>
          ) : (
            <>
              No account yet?{" "}
              <Link href="/signup" className="font-medium text-primary underline-offset-4 hover:underline">
                Create one
              </Link>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
