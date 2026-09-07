import { Activity, BarChart3, CircleDollarSign, Gauge, Percent, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";

import { BankrollChart } from "@/components/charts/bankroll-chart";
import { MetricCard } from "@/components/features/metric-card";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { percent } from "@/lib/utils";

export const metadata: Metadata = { title: "Performance" };
export const dynamic = "force-dynamic";

type Performance = { data_mode: "real" | "simulation"; metrics: Record<string, number | null>; bankroll_history: Array<{ timestamp: string; bankroll: number; change: number }>; segments: Array<{ segment: string; bets: number; roi: number; clv: number | null; brier_score: number | null; enabled: boolean }> };

export default async function PerformancePage() {
  const data = await apiFetch<Performance>("/performance");
  const m = data.metrics;
  return <div className="space-y-6"><PageHeader eyebrow="Model monitoring" title="Measured performance, not hit-rate theatre" description="ROI, yield, CLV and calibration are tracked by version and segment. Closing prices are evaluation targets, never pre-match features." /><section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6"><MetricCard label="Total bets" value={m.total_bets ?? 0} icon={BarChart3} /><MetricCard label="Win rate" value={percent(m.win_rate)} icon={Activity} /><MetricCard label="ROI" value={percent(m.roi)} icon={Percent} positive /><MetricCard label="Profit" value={`€${(m.profit ?? 0).toFixed(2)}`} icon={CircleDollarSign} positive /><MetricCard label="Average CLV" value={percent(m.average_clv)} icon={Gauge} positive /><MetricCard label="Max drawdown" value={percent(m.max_drawdown)} icon={ShieldCheck} /></section><section className="grid gap-4 xl:grid-cols-[1.5fr_1fr]"><Card><CardHeader><CardTitle>Cumulative bankroll</CardTitle><p className="text-xs text-slate-600">Settled results only</p></CardHeader><CardContent><BankrollChart data={data.bankroll_history} /></CardContent></Card><Card><CardHeader><CardTitle>Calibration health</CardTitle><p className="text-xs text-slate-600">Lower is better</p></CardHeader><CardContent className="space-y-5"><Score label="Brier score" value={m.brier_score?.toFixed(3) ?? "—"} note="Squared probability error" /><Score label="Log loss" value={m.log_loss?.toFixed(3) ?? "—"} note="Penalizes confident mistakes" /><Score label="Average edge" value={percent(m.average_edge)} note="Prediction-time edge" /></CardContent></Card></section><Card><CardHeader><CardTitle>Performance by segment</CardTitle></CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="border-y border-border text-[9px] uppercase tracking-wider text-slate-600"><tr><th className="py-3">Segment</th><th>Bets</th><th>ROI</th><th>CLV</th><th>Brier</th><th>Status</th></tr></thead><tbody>{data.segments.map((row) => <tr key={row.segment} className="border-b border-border"><td className="py-4 text-slate-300">{row.segment}</td><td className="number">{row.bets}</td><td className="number text-emerald-300">{percent(row.roi)}</td><td className="number">{percent(row.clv)}</td><td className="number">{row.brier_score?.toFixed(3) ?? "—"}</td><td><Badge variant={row.enabled ? "default" : "danger"}>{row.enabled ? "Enabled" : "Review"}</Badge></td></tr>)}</tbody></table></div></CardContent></Card></div>;
}

function Score({ label, value, note }: { label: string; value: string; note: string }) { return <div className="flex items-end justify-between border-b border-border pb-4"><div><p className="text-xs font-medium text-slate-300">{label}</p><p className="mt-1 text-[10px] text-slate-600">{note}</p></div><p className="number text-xl font-semibold">{value}</p></div>; }
