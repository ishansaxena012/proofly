import { Suspense } from "react";
import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your Proofly account to start and review research jobs.",
};

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthFormSkeleton />}>
      <AuthForm mode="login" />
    </Suspense>
  );
}

function AuthFormSkeleton() {
  return (
    <div className="container flex justify-center py-16 sm:py-24">
      <div className="w-full max-w-md space-y-6">
        <Skeleton className="mx-auto h-9 w-40" />
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  );
}
