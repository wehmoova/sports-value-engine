import { AlertTriangle, CheckCircle2, Database, Timer } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import { ModelComparisonChart } from "@/components/charts/model-comparison-chart";
import { OddsMovementChart } from "@/components/charts/odds-movement-chart";
import { ScoreBadge } from "@/components/features/score-badge";
import { EventSources } from "@/components/features/event-sources";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { compactTime, decimal, percent } from "@/lib/utils";
import type { EventDetail } from "@/types";

export const dynamic = "force-dynamic";
const getEvent = cache(async (id: string) => {
  try { return await apiFetch<EventDetail>(`/events/${id}`); } catch { return null; }
});

export async function generateMetadata({ params }: PageProps<"/events/[id]">): Promise<Metadata> {
  const { id } = await params;
  const event = await getEvent(id);
  if (!event) return { title: "Event not found" };
  const description = `${event.competition}: model pricing, market consensus and data quality for ${event.name}.`;
  return { title: event.name, description, openGraph: { title: event.name, description, images: [] }, twitter: { title: event.name, description, images: [] } };
}

export default async function EventPage({ params }: PageProps<"/events/[id]">) {
  const { id } = await params;
  const event = await getEvent(id);
  if (!event) notFound();
  const verdict = event.recommendations[0];
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={event.competition} title={event.name} description={`${event.surface ? `${event.surface} · ` : ""}${event.round ? `${event.round} · ` : ""}${compactTime(event.start_time)} · ${event.status}`} updatedAt={event.source_timestamp} />
      <EventSources event={event} />
      {verdict ? <>
        <Card className={verdict.status === "VALUE" ? "border-emerald-400/20" : "border-red-400/20"}>
          <CardHeader className="flex-row items-center justify-between border-b border-border"><div><Badge variant={verdict.status === "VALUE" ? "default" : "danger"}>Model verdict · {verdict.status.replace("_", " ")}</Badge><CardTitle className="mt-3 text-lg">{verdict.selection}</CardTitle><p className="mt-1 text-xs text-slate-500">{verdict.market} · best price at {verdict.bookmaker}</p></div><div className="text-right"><p className="text-[9px] uppercase tracking-wider text-slate-600">Best odds</p><p className="number text-4xl font-semibold text-slate-50">{decimal(verdict.best_odds)}</p></div></CardHeader>
          <CardContent className="grid gap-5 pt-5 lg:grid-cols-[1.2fr_1fr]">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5"><VerdictStat label="Model" value={percent(verdict.model_probability)} /><VerdictStat label="Market" value={percent(verdict.market_probability)} /><VerdictStat label="Fair odds" value={decimal(verdict.fair_odds)} /><VerdictStat label="Edge" value={`+${percent(verdict.edge)}`} positive /><VerdictStat label="Expected value" value={`+${percent(verdict.expected_value)}`} positive /></div>
            <div className="grid grid-cols-2 gap-5"><ScoreBadge label="Confidence" value={verdict.confidence_score} /><ScoreBadge label="Data quality" value={verdict.data_quality_score} /></div>
          </CardContent>
        </Card>
        <section className="grid gap-4 xl:grid-cols-2">
          <Card><CardHeader><CardTitle>Model comparison</CardTitle><p className="text-xs text-slate-600">Independent outputs reveal disagreement before ensemble weighting</p></CardHeader><CardContent><ModelComparisonChart components={verdict.model_components} market={verdict.market_probability} /></CardContent></Card>
          <Card><CardHeader><CardTitle>Price movement</CardTitle><p className="text-xs text-slate-600">Actual snapshots for {verdict.bookmaker}; no interpolated observations</p></CardHeader><CardContent><OddsMovementChart snapshots={event.odds.filter(odd => odd.bookmaker === verdict.bookmaker && odd.market === verdict.market && odd.selection === verdict.selection && !odd.is_outlier)} /></CardContent></Card>
        </section>
        <section className="grid gap-4 xl:grid-cols-2">
          <Card><CardHeader><CardTitle className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" />Why this price?</CardTitle></CardHeader><CardContent><ul className="space-y-3">{verdict.positive_factors.map((factor) => <li key={factor} className="flex gap-3 text-xs text-slate-400"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />{factor}</li>)}</ul></CardContent></Card>
          <Card><CardHeader><CardTitle className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-400" />Risks</CardTitle></CardHeader><CardContent><ul className="space-y-3">{verdict.risks.map((risk) => <li key={risk} className="flex gap-3 text-xs text-slate-400"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />{risk}</li>)}</ul></CardContent></Card>
        </section>
        <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Odds comparison</CardTitle><p className="mt-1 text-xs text-slate-600">Every source retains provider and observation time</p></div><Database className="h-4 w-4 text-slate-600" /></CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="border-y border-border text-[9px] uppercase tracking-wider text-slate-600"><tr><th className="py-3">Bookmaker</th><th>Market</th><th>Selection</th><th>Price</th><th>Observed</th></tr></thead><tbody className="divide-y divide-border">{event.odds.map((odd, index) => <tr key={`${odd.bookmaker}-${odd.selection}-${index}`} className={odd.is_outlier ? "opacity-40" : ""}><td className="py-3 text-slate-300">{odd.bookmaker}</td><td className="text-slate-500">{odd.market}</td><td className="text-slate-400">{odd.selection}</td><td className="number font-semibold text-slate-100">{decimal(odd.decimal_odds)}</td><td className="text-slate-600">{compactTime(odd.observed_at)}</td></tr>)}</tbody></table></div></CardContent></Card>
        <div className="flex flex-wrap items-center gap-4 text-[9px] uppercase tracking-wider text-slate-700"><span className="flex items-center gap-1.5"><Database className="h-3 w-3" />{verdict.model_version}</span><span className="flex items-center gap-1.5"><Timer className="h-3 w-3" />Odds {compactTime(verdict.odds_timestamp)}</span><span>Features {verdict.feature_version}</span></div>
      </> : <Card><CardContent className="grid min-h-64 place-items-center p-8 text-center"><div><p className="text-sm font-semibold">Model verdict pending</p><p className="mt-2 max-w-lg text-xs leading-relaxed text-slate-600">Odds are stored, but the statistical feature set is incomplete. The engine will not infer a probability from price alone.</p></div></CardContent></Card>}
    </div>
  );
}

function VerdictStat({ label, value, positive = false }: { label: string; value: string; positive?: boolean }) { return <div className="rounded-lg border border-border bg-slate-950/35 p-3"><p className="text-[9px] uppercase tracking-wider text-slate-600">{label}</p><p className={`number mt-2 text-base font-semibold ${positive ? "text-emerald-300" : "text-slate-100"}`}>{value}</p></div>; }
