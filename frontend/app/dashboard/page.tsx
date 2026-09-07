import { Activity, Gauge, Percent, Radar, ShieldCheck, Trophy } from "lucide-react";

import { EdgeChart } from "@/components/charts/edge-chart";
import { CombinationCard } from "@/components/features/combination-card";
import { EmptyState } from "@/components/features/event-table";
import { MetricCard } from "@/components/features/metric-card";
import { PickCard } from "@/components/features/pick-card";
import { DataAvailabilityNotice } from "@/components/layout/data-availability-notice";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { percent } from "@/lib/utils";
import type { Dashboard } from "@/types";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const data = await apiFetch<Dashboard>("/dashboard");
  const metrics = data.metrics;
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Today’s market analysis" title="Decision-grade sports pricing" description="Independent model probabilities compared with de-vigged market consensus. Value is shown only when price, confidence and data-quality thresholds agree." updatedAt={data.last_refresh} />
      <DataAvailabilityNotice configured={data.provider_configured} />
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <MetricCard label="Events analysed" value={metrics.events_analysed} detail={`${metrics.football_events} football · ${metrics.tennis_events} tennis`} icon={Radar} />
        <MetricCard label="Value opportunities" value={metrics.value_opportunities} detail="Passed every threshold" icon={Activity} positive />
        <MetricCard label="Strong picks" value={metrics.strong_picks} detail="Confidence ≥ 80" icon={ShieldCheck} positive />
        <MetricCard label="Average edge" value={`+${percent(metrics.average_edge)}`} detail="Percentage points" icon={Gauge} positive />
        <MetricCard label="Average EV" value={`+${percent(metrics.average_ev)}`} detail="At best available price" icon={Percent} positive />
        <MetricCard label="Analysis run" value={data.analysis_run?.status ?? "—"} detail={`${data.analysis_run?.events_processed ?? 0} processed`} icon={Trophy} />
      </section>

      <section>
        <SectionHeading title="Top value opportunities" detail="Ranked by expected value after quality gates" />
        {data.top_picks.length ? <div className="grid gap-4 xl:grid-cols-2">{data.top_picks.map((pick) => <PickCard key={pick.id} pick={pick} />)}</div> : <EmptyState title="No qualified value today" detail="No bet is a valid output. Candidates appear only when every configured threshold is met." />}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader className="flex-row items-start justify-between"><div><CardTitle>Model vs market</CardTitle><p className="mt-1 text-xs text-slate-600">Probability gap across today’s leading selections</p></div><div className="flex gap-3 text-[9px] uppercase tracking-wider"><span className="flex items-center gap-1.5 text-slate-500"><i className="h-2 w-2 rounded-sm bg-slate-700" />Market</span><span className="flex items-center gap-1.5 text-emerald-300"><i className="h-2 w-2 rounded-sm bg-emerald-400" />Model</span></div></CardHeader>
          <CardContent><EdgeChart picks={data.top_picks} /></CardContent>
        </Card>
        <div><SectionHeading title="Best combination" detail="Qualified singles only" />{data.combinations[0] ? <CombinationCard combination={data.combinations[0]} /> : <EmptyState title="No valid combination" detail="At least two independent qualifying selections are required." />}</div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div><SectionHeading title="Football opportunities" detail="Poisson · Elo · xG · Ensemble" />{data.football_opportunities.length ? <div className="space-y-4">{data.football_opportunities.map((pick) => <PickCard key={pick.id} pick={pick} />)}</div> : <EmptyState title="No football value" detail="Current prices do not clear the decision thresholds." />}</div>
        <div><SectionHeading title="Tennis opportunities" detail="Overall Elo · Surface Elo · Serve/Return" />{data.tennis_opportunities.length ? <div className="space-y-4">{data.tennis_opportunities.map((pick) => <PickCard key={pick.id} pick={pick} />)}</div> : <EmptyState title="No tennis value" detail="Current prices do not clear the decision thresholds." />}</div>
      </section>
    </div>
  );
}

function SectionHeading({ title, detail }: { title: string; detail: string }) {
  return <div className="mb-3 flex items-end justify-between"><div><h2 className="text-sm font-semibold text-slate-200">{title}</h2><p className="mt-1 text-[10px] uppercase tracking-wider text-slate-600">{detail}</p></div></div>;
}
