import type { Metadata } from "next";

import { ReportView } from "@/components/report/report-view";

export const metadata: Metadata = {
  title: "Research report",
  description:
    "An evidence-backed Proofly report: verdict, category scores, conflicting opinions and every source behind them.",
};

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReportView researchJobId={id} />;
}
