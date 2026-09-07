"use client";

import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/features/event-table";
import { PickCard } from "@/components/features/pick-card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { Recommendation } from "@/types";

export function PicksBrowser({ picks }: { picks: Recommendation[] }) {
  const [query, setQuery] = useState("");
  const [sport, setSport] = useState("all");
  const [sort, setSort] = useState("ev");
  const [minimumEv, setMinimumEv] = useState(0.03);
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return picks
      .filter((pick) => !needle || `${pick.event} ${pick.selection} ${pick.competition}`.toLowerCase().includes(needle))
      .filter((pick) => sport === "all" || (sport === "tennis" ? pick.sport.startsWith("tennis") : pick.sport === sport))
      .filter((pick) => pick.expected_value >= minimumEv)
      .sort((a, b) => {
        if (sort === "edge") return b.edge - a.edge;
        if (sort === "confidence") return b.confidence_score - a.confidence_score;
        if (sort === "start") return new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
        return b.expected_value - a.expected_value;
      });
  }, [minimumEv, picks, query, sort, sport]);
  return <div className="space-y-5"><div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3 lg:flex-row lg:items-center"><div className="relative min-w-64 flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-600" /><Input className="pl-9" placeholder="Search event or selection" aria-label="Search picks" value={query} onChange={(event) => setQuery(event.target.value)} /></div><Select aria-label="Filter sport" value={sport} onChange={(event) => setSport(event.target.value)}><option value="all">All sports</option><option value="football">Football</option><option value="tennis">Tennis</option></Select><label className="flex items-center gap-2 rounded-md border border-border bg-slate-950/40 px-3"><span className="whitespace-nowrap text-[10px] uppercase tracking-wider text-slate-600">Min EV</span><Input className="w-20 border-0 bg-transparent px-1" type="number" min="0" max="2" step="0.01" value={minimumEv} onChange={(event) => setMinimumEv(Number(event.target.value))} /></label><Select aria-label="Sort picks" value={sort} onChange={(event) => setSort(event.target.value)}><option value="ev">Highest EV</option><option value="edge">Highest edge</option><option value="confidence">Highest confidence</option><option value="start">Start time</option></Select></div><p className="text-[10px] uppercase tracking-[0.14em] text-slate-600">{visible.length} qualified selections · client-side filtered</p>{visible.length ? <div className="grid gap-4 xl:grid-cols-2">{visible.map((pick) => <PickCard key={pick.id} pick={pick} />)}</div> : <EmptyState title="No selections match these filters" detail="Reduce the minimum EV or broaden the sport and search filters." />}</div>;
}

