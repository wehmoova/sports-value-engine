import type { Metadata } from "next";

import { CombinationCard } from "@/components/features/combination-card";
import { EmptyState } from "@/components/features/event-table";
import { PageHeader } from "@/components/layout/page-header";
import { apiFetch } from "@/lib/api";
import type { Combination } from "@/types";

export const metadata: Metadata = { title: "Combinations" };
export const dynamic = "force-dynamic";

export default async function CombinationsPage() {
  const combinations = await apiFetch<Combination[]>("/combinations");
  return <div className="space-y-6"><PageHeader eyebrow="Portfolio construction" title="Disciplined combinations" description="Only individually qualified value selections can become a leg. Combinations are capped at three legs in the MVP and show the independence assumption explicitly." />{combinations.length ? <div className="grid gap-4 xl:grid-cols-2">{combinations.map((item) => <CombinationCard key={item.id} combination={item} />)}</div> : <EmptyState title="No responsible combination available" detail="At least two qualified selections from separate events are required." />}</div>;
}
