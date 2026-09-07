import type { Metadata } from "next";

import { EventTable } from "@/components/features/event-table";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import type { EventSummary } from "@/types";

export const metadata: Metadata = { title: "Tennis" };
export const dynamic = "force-dynamic";

export default async function TennisPage() {
  const events = await apiFetch<EventSummary[]>("/tennis/events");
  return <div className="space-y-6"><PageHeader eyebrow="ATP · WTA" title="Tennis market board" description="Surface-weighted Elo, serve/return strength and opponent-adjusted recent form. Workload and injury uncertainty remain risk modifiers, never standalone tips." /><Card><CardContent className="flex flex-wrap gap-2 p-4"><Badge variant="blue">ATP + WTA</Badge><Badge variant="neutral">All surfaces</Badge><Badge variant="neutral">Main draw</Badge><Badge variant="neutral">Moneyline</Badge></CardContent></Card><EventTable events={events} /></div>;
}
