import type { Metadata } from "next";

import { PicksBrowser } from "@/components/features/picks-browser";
import { PageHeader } from "@/components/layout/page-header";
import { apiFetch } from "@/lib/api";
import type { Recommendation } from "@/types";

export const metadata: Metadata = { title: "Today's Picks" };
export const dynamic = "force-dynamic";

export default async function PicksPage() {
  const picks = await apiFetch<Recommendation[]>("/picks/today");
  return <div className="space-y-6"><PageHeader eyebrow="Qualified singles" title="Today’s value candidates" description="Every visible candidate clears minimum price, edge, EV, confidence and data-quality gates. A high win probability without a fair market price is excluded." /><PicksBrowser picks={picks} /></div>;
}
