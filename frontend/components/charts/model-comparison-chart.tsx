"use client";

import { CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, Bar, BarChart } from "recharts";

export function ModelComparisonChart({ components, market }: { components: Record<string, number>; market: number }) {
  const data = Object.entries(components).map(([name, probability]) => ({ name, probability: Math.round(probability * 1000) / 10 }));
  return <div className="h-64 w-full"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} layout="vertical" margin={{ top: 4, right: 18, left: 12, bottom: 0 }}><CartesianGrid horizontal={false} stroke="#19222d" /><XAxis type="number" domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: "#566273", fontSize: 10 }} /><YAxis type="category" dataKey="name" width={92} axisLine={false} tickLine={false} tick={{ fill: "#8290a2", fontSize: 10 }} /><Tooltip cursor={{ fill: "rgba(148,163,184,.04)" }} contentStyle={{ background: "#0c1119", border: "1px solid #1a2430", borderRadius: 8, fontSize: 11 }} /><ReferenceLine x={market * 100} stroke="#60a5fa" strokeDasharray="3 3" label={{ value: "market", fill: "#60a5fa", fontSize: 9 }} /><Bar dataKey="probability" fill="#34d399" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer></div>;
}

