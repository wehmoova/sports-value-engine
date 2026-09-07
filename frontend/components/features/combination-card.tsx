import { AlertTriangle, Link2 } from "lucide-react";

import { ScoreBadge } from "@/components/features/score-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { decimal, percent } from "@/lib/utils";
import type { Combination } from "@/types";

export function CombinationCard({ combination }: { combination: Combination }) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between border-b border-border"><div><Badge variant="blue">{combination.category.replace("_", " ")}</Badge><CardTitle className="mt-3">{combination.legs.length}-leg combination</CardTitle></div><div className="text-right"><p className="text-[9px] uppercase tracking-wider text-slate-600">Combined odds</p><p className="number mt-1 text-2xl font-semibold">{decimal(combination.combined_odds)}</p></div></CardHeader>
      <CardContent className="pt-5">
        <div className="space-y-3">{combination.legs.map((leg, index) => <div key={leg.id} className="flex items-center gap-3"><span className="number grid h-6 w-6 place-items-center rounded bg-slate-800 text-[10px] text-slate-400">{index + 1}</span><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium text-slate-200">{leg.selection}</p><p className="truncate text-[10px] text-slate-600">{leg.event}</p></div><span className="number text-xs text-slate-300">{decimal(leg.best_odds)}</span></div>)}</div>
        <div className="my-5 grid grid-cols-2 gap-3 rounded-lg bg-slate-950/40 p-3"><Stat label="Est. probability" value={percent(combination.combined_probability)} /><Stat label="Combined EV" value={`+${percent(combination.combined_ev)}`} positive /></div>
        <ScoreBadge label="Confidence" value={combination.confidence_score} />
        {combination.correlation_warning && <div className="mt-4 flex gap-2 rounded-md border border-amber-400/15 bg-amber-400/[0.04] p-3 text-[10px] leading-relaxed text-amber-200/70"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{combination.correlation_warning}</div>}
        <div className="mt-3 flex items-center gap-1.5 text-[9px] uppercase tracking-wider text-slate-700"><Link2 className="h-3 w-3" />Qualified single picks only</div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, positive = false }: { label: string; value: string; positive?: boolean }) {
  return <div><p className="text-[9px] uppercase tracking-wider text-slate-600">{label}</p><p className={`number mt-1 text-sm font-semibold ${positive ? "text-emerald-300" : "text-slate-200"}`}>{value}</p></div>;
}

