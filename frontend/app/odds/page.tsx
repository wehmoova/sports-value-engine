import { Activity, ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { Metadata } from "next";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { decimal, percent } from "@/lib/utils";
import type { Recommendation } from "@/types";

export const metadata: Metadata = { title: "Odds Movement" };
export const dynamic = "force-dynamic";

export default async function OddsPage() {
  const [value, noBet] = await Promise.all([apiFetch<Recommendation[]>("/picks?status=VALUE"), apiFetch<Recommendation[]>("/picks?status=NO_BET")]);
  const picks = [...value, ...noBet];
  return <div className="space-y-6"><PageHeader eyebrow="Market microstructure" title="Price and line movement" description="Opening, current and consensus prices are timestamped. Movement is treated as information, never a standalone betting trigger." /><Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Largest tracked movements</CardTitle><p className="mt-1 text-xs text-slate-600">Best available price versus opening snapshot</p></div><Activity className="h-4 w-4 text-sky-400" /></CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="border-y border-border text-[9px] uppercase tracking-wider text-slate-600"><tr><th className="py-3">Selection</th><th>Market</th><th>Opening</th><th>Current</th><th>Change</th><th>Consensus</th><th>Best book</th><th>Verdict</th></tr></thead><tbody>{picks.map((pick) => { const opening = pick.opening_odds ?? pick.best_odds; const change = pick.best_odds / opening - 1; const Falling = change < 0 ? ArrowDownRight : ArrowUpRight; return <tr key={pick.id} className="border-b border-border"><td className="py-4"><p className="font-medium text-slate-200">{pick.selection}</p><p className="mt-1 text-[10px] text-slate-600">{pick.event}</p></td><td className="text-slate-500">{pick.market}</td><td className="number">{decimal(opening)}</td><td className="number font-semibold text-slate-100">{decimal(pick.best_odds)}</td><td><span className={`number flex items-center gap-1 ${change >= 0 ? "text-emerald-300" : "text-amber-300"}`}><Falling className="h-3.5 w-3.5" />{percent(change)}</span></td><td className="number text-slate-400">{decimal(pick.median_odds)}</td><td className="text-slate-500">{pick.bookmaker}</td><td><Badge variant={pick.status === "VALUE" ? "default" : "danger"}>{pick.status.replace("_", " ")}</Badge></td></tr>; })}</tbody></table></div></CardContent></Card></div>;
}
