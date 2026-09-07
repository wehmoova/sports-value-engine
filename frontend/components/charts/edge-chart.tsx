"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Recommendation } from "@/types";

export function EdgeChart({ picks }: { picks: Recommendation[] }) {
  const data = picks.map((pick) => ({ name: pick.selection.split(" ").slice(0, 2).join(" "), Model: Math.round(pick.model_probability * 1000) / 10, Market: Math.round(pick.market_probability * 1000) / 10 }));
  return <div className="h-64 w-full"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ top: 8, right: 0, left: -22, bottom: 0 }}><CartesianGrid vertical={false} stroke="#19222d" /><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#647184", fontSize: 10 }} /><YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: "#566273", fontSize: 10 }} /><Tooltip cursor={{ fill: "rgba(148,163,184,.04)" }} contentStyle={{ background: "#0c1119", border: "1px solid #1a2430", borderRadius: 8, fontSize: 11 }} /><Bar dataKey="Market" fill="#334155" radius={[3, 3, 0, 0]} /><Bar dataKey="Model" fill="#34d399" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div>;
}

