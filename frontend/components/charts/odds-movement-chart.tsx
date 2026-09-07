"use client";

import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function OddsMovementChart({ snapshots }: { snapshots: Array<{ observed_at: string; decimal_odds: number }> }) {
  const data = snapshots.map(snapshot => ({ time: new Date(snapshot.observed_at).toLocaleString("de-DE"), odds: snapshot.decimal_odds }));
  if (data.length < 2) return <p className="py-12 text-center text-xs text-slate-500">At least two actual price snapshots are required.</p>;
  return <div className="h-64 w-full"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}><CartesianGrid vertical={false} stroke="#19222d" /><XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: "#566273", fontSize: 10 }} /><YAxis domain={["dataMin - 0.1", "dataMax + 0.1"]} axisLine={false} tickLine={false} tick={{ fill: "#566273", fontSize: 10 }} /><Tooltip contentStyle={{ background: "#0c1119", border: "1px solid #1a2430", borderRadius: 8, fontSize: 11 }} /><Line type="monotone" dataKey="odds" stroke="#60a5fa" strokeWidth={2} dot={{ fill: "#0c1119", stroke: "#60a5fa", strokeWidth: 2, r: 4 }} /></LineChart></ResponsiveContainer></div>;
}
