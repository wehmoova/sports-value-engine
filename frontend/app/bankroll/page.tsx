import { CircleDollarSign, Gauge, ShieldCheck, TrendingUp } from "lucide-react";
import type { Metadata } from "next";

import { BankrollChart } from "@/components/charts/bankroll-chart";
import { MetricCard } from "@/components/features/metric-card";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { compactTime, percent } from "@/lib/utils";

export const metadata: Metadata = { title: "Bankroll" };
export const dynamic = "force-dynamic";

type Bankroll = { starting_bankroll: number; current_bankroll: number; profit: number; roi: number; current_drawdown: number; data_mode: "real" | "simulation"; history: Array<{ timestamp: string; bankroll: number; change: number; reason: string }> };

export default async function BankrollPage() {
  const data = await apiFetch<Bankroll>("/bankroll");
  return <div className="space-y-6"><PageHeader eyebrow="Capital discipline" title="Bankroll ledger" description="Flat 0.5–1% staking is the default reference. No martingale, loss chasing or automatic Kelly sizing is applied." /><section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><MetricCard label="Starting bankroll" value={`€${data.starting_bankroll.toFixed(2)}`} icon={CircleDollarSign} /><MetricCard label="Current bankroll" value={`€${data.current_bankroll.toFixed(2)}`} icon={TrendingUp} positive /><MetricCard label="Return" value={percent(data.roi)} icon={Gauge} positive /><MetricCard label="Current drawdown" value={percent(data.current_drawdown)} icon={ShieldCheck} /></section><Card><CardHeader><CardTitle>Bankroll curve</CardTitle></CardHeader><CardContent><BankrollChart data={data.history} /></CardContent></Card><Card><CardHeader><CardTitle>Recent ledger entries</CardTitle></CardHeader><CardContent><div className="divide-y divide-border">{data.history.slice().reverse().slice(0, 8).map((point) => <div key={point.timestamp} className="flex items-center justify-between py-3 text-xs"><div><p className="text-slate-300">{point.reason.replaceAll("_", " ")}</p><p className="mt-1 text-[10px] text-slate-600">{compactTime(point.timestamp)}</p></div><div className="text-right"><p className={`number ${point.change >= 0 ? "text-emerald-300" : "text-red-300"}`}>{point.change >= 0 ? "+" : ""}€{point.change.toFixed(2)}</p><p className="number mt-1 text-[10px] text-slate-600">€{point.bankroll.toFixed(2)}</p></div></div>)}</div></CardContent></Card></div>;
}
