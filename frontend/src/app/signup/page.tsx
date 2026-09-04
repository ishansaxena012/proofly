import { Suspense } from "react";
import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create a Proofly account to run evidence-backed product research.",
};

export default function SignupPage() {
  return (
    <Suspense fallback={<AuthFormSkeleton />}>
      <AuthForm mode="signup" />
    </Suspense>
  );
}

function AuthFormSkeleton() {
  return (
    <div className="container flex justify-center py-16 sm:py-24">
      <div className="w-full max-w-md space-y-6">
        <Skeleton className="mx-auto h-9 w-56" />
        <Skeleton className="h-80 w-full" />
      </div>
    </div>
  );
}
