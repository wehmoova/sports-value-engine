"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function BankrollChart({ data }: { data: Array<{ timestamp: string; bankroll: number }> }) {
  const formatted = data.map((point) => ({ ...point, date: new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "short" }).format(new Date(point.timestamp)) }));
  return <div className="h-72 w-full"><ResponsiveContainer width="100%" height="100%"><AreaChart data={formatted} margin={{ top: 10, right: 6, left: -8, bottom: 0 }}><defs><linearGradient id="bankrollFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#34d399" stopOpacity={0.24} /><stop offset="95%" stopColor="#34d399" stopOpacity={0} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#19222d" /><XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#566273", fontSize: 10 }} /><YAxis domain={["dataMin - 20", "dataMax + 20"]} axisLine={false} tickLine={false} tick={{ fill: "#566273", fontSize: 10 }} /><Tooltip contentStyle={{ background: "#0c1119", border: "1px solid #1a2430", borderRadius: 8, fontSize: 11 }} /><Area type="monotone" dataKey="bankroll" stroke="#34d399" strokeWidth={2} fill="url(#bankrollFill)" /></AreaChart></ResponsiveContainer></div>;
}

