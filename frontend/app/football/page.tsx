import type { Metadata } from "next";

import { EventTable } from "@/components/features/event-table";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import type { EventSummary } from "@/types";

export const metadata: Metadata = { title: "Football" };
export const dynamic = "force-dynamic";

export default async function FootballPage() {
  const events = await apiFetch<EventSummary[]>("/football/events");
  return <div className="space-y-6"><PageHeader eyebrow="Football models" title="Football market board" description="Pre-match 1X2 and moneyline pricing backed by separate Poisson, Elo and xG signals. Missing xG or lineup data lowers quality instead of being inferred." /><Card><CardContent className="flex flex-wrap gap-2 p-4"><Badge variant="blue">All leagues</Badge><Badge variant="neutral">1X2</Badge><Badge variant="neutral">Minimum edge 3%</Badge><Badge variant="neutral">Confidence ≥ 70</Badge></CardContent></Card><EventTable events={events} /></div>;
}
