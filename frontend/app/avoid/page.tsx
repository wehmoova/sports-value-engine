import { CircleOff } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/features/event-table";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { decimal, percent } from "@/lib/utils";
import type { Recommendation } from "@/types";

export const metadata: Metadata = { title: "No Bet" };
export const dynamic = "force-dynamic";

const reasons: Record<string, string> = { PRICE_TOO_SHORT: "High model probability, but the available price is too short.", EDGE_BELOW_THRESHOLD: "The model advantage does not clear the minimum edge.", EV_BELOW_THRESHOLD: "Expected value remains below the configured threshold.", LOW_CONFIDENCE: "Model agreement or input certainty is insufficient.", INSUFFICIENT_DATA: "Critical feature coverage is missing or stale." };

export default async function AvoidPage() {
  const items = await apiFetch<Recommendation[]>("/no-bet");
  return <div className="space-y-6"><PageHeader eyebrow="Price discipline" title="No-bet ledger" description="Interesting events rejected by the engine. This view makes clear why likely outcomes can still be poor wagers." />{items.length ? <div className="grid gap-4 lg:grid-cols-2">{items.map((item) => <Card key={item.id}><CardContent className="p-5"><div className="flex items-start justify-between"><div><Badge variant="danger"><CircleOff className="mr-1 h-3 w-3" />No value</Badge><h2 className="mt-3 text-sm font-semibold">{item.selection}</h2><p className="mt-1 text-xs text-slate-600">{item.event}</p></div><p className="number text-2xl font-semibold text-slate-300">{decimal(item.best_odds)}</p></div><div className="my-4 grid grid-cols-3 gap-3 rounded-lg bg-slate-950/40 p-3"><Stat label="Model" value={percent(item.model_probability)} /><Stat label="Market" value={percent(item.market_probability)} /><Stat label="Fair odds" value={decimal(item.fair_odds)} /></div><p className="text-xs leading-relaxed text-slate-400">{reasons[item.reason_code] ?? item.reason_code}</p>{item.desired_entry_odds && <p className="mt-3 text-[10px] uppercase tracking-wider text-sky-300">Watch from {decimal(item.desired_entry_odds)}+</p>}</CardContent></Card>)}</div> : <EmptyState title="No rejected candidates" detail="Rejected price candidates will appear after model evaluation." />}</div>;
}

function Stat({ label, value }: { label: string; value: string }) { return <div><p className="text-[9px] uppercase tracking-wider text-slate-600">{label}</p><p className="number mt-1 text-xs text-slate-200">{value}</p></div>; }
