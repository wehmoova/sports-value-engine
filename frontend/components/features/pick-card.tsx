import { ArrowUpRight, Clock3, LineChart } from "lucide-react";
import Link from "next/link";

import { ScoreBadge } from "@/components/features/score-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { compactTime, decimal, percent } from "@/lib/utils";
import type { Recommendation } from "@/types";

export function PickCard({ pick }: { pick: Recommendation }) {
  return (
    <Card className="group overflow-hidden transition-colors hover:border-slate-600/60">
      <div className="flex items-center justify-between border-b border-border bg-slate-950/35 px-4 py-2.5">
        <div className="flex items-center gap-2"><Badge variant={pick.sport === "football" ? "blue" : "neutral"}>{pick.sport.replace("_", " ")}</Badge><span className="max-w-[180px] truncate text-[10px] text-slate-500">{pick.competition}</span></div>
        <div className="flex items-center gap-1 text-[10px] text-slate-600"><Clock3 className="h-3 w-3" />{compactTime(pick.start_time)}</div>
      </div>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-100">{pick.event}</p><p className="mt-1 text-[10px] uppercase tracking-wider text-slate-600">{pick.market}</p><p className="mt-2 text-sm font-medium text-emerald-300">{pick.selection}</p></div>
          <div className="shrink-0 text-right"><p className="text-[9px] uppercase tracking-wider text-slate-600">Best price</p><p className="number mt-1 text-2xl font-semibold text-slate-50">{decimal(pick.best_odds)}</p><p className="text-[9px] text-slate-600">{pick.bookmaker}</p></div>
        </div>
        <div className="mt-4 grid grid-cols-4 gap-2 rounded-lg border border-border bg-slate-950/40 p-3">
          <Stat label="Model" value={percent(pick.model_probability, 0)} />
          <Stat label="Market" value={percent(pick.market_probability, 0)} />
          <Stat label="Edge" value={`+${percent(pick.edge)}`} positive />
          <Stat label="EV" value={`+${percent(pick.expected_value)}`} positive />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4"><ScoreBadge label="Confidence" value={pick.confidence_score} /><ScoreBadge label="Data quality" value={pick.data_quality_score} /></div>
        <div className="mt-4 flex items-center justify-between border-t border-border pt-3"><div className="flex items-center gap-1.5 text-[10px] text-slate-600"><LineChart className="h-3.5 w-3.5" />Fair odds <span className="number text-slate-300">{decimal(pick.fair_odds)}</span></div><Button asChild variant="ghost" size="sm"><Link href={`/events/${pick.event_id}`}>View analysis <ArrowUpRight className="h-3.5 w-3.5" /></Link></Button></div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, positive = false }: { label: string; value: string; positive?: boolean }) {
  return <div><p className="text-[9px] uppercase tracking-wider text-slate-600">{label}</p><p className={`number mt-1 text-xs font-semibold ${positive ? "text-emerald-300" : "text-slate-200"}`}>{value}</p></div>;
}

