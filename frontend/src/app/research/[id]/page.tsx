import type { Metadata } from "next";

import { ResearchProgressView } from "@/components/research/research-progress-view";

export const metadata: Metadata = {
  title: "Research progress",
  description: "Live pipeline progress for a Proofly research job.",
};

export default async function ResearchJobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ResearchProgressView researchJobId={id} />;
}
