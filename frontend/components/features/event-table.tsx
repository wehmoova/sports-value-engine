import { ArrowUpRight, CalendarClock } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { compactTime, decimal, percent } from "@/lib/utils";
import type { EventSummary } from "@/types";

export function EventTable({ events }: { events: EventSummary[] }) {
  if (!events.length) return <EmptyState title="No events in this window" detail="Events appear after a configured provider refresh." />;
  return (
    <Card className="overflow-hidden">
      <div className="hidden grid-cols-[130px_minmax(260px,1fr)_150px_110px_100px_46px] gap-4 border-b border-border bg-slate-950/40 px-4 py-2.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-600 md:grid"><span>Start</span><span>Event</span><span>Competition</span><span>Verdict</span><span>Price / Edge</span><span /></div>
      <div className="divide-y divide-border">
        {events.map((event) => (
          <div key={event.id} className="grid gap-3 px-4 py-4 transition-colors hover:bg-slate-900/30 md:grid-cols-[130px_minmax(260px,1fr)_150px_110px_100px_46px] md:items-center md:gap-4">
            <div className="flex items-center gap-2 text-[11px] text-slate-500"><CalendarClock className="h-3.5 w-3.5" />{compactTime(event.start_time)}</div>
            <div><p className="text-sm font-medium text-slate-200">{event.name}</p><div className="mt-1 flex gap-2"><span className="text-[10px] uppercase tracking-wider text-slate-600">{event.sport.replace("_", " ")}</span>{event.surface && <span className="text-[10px] text-sky-400">{event.surface}</span>}</div></div>
            <p className="truncate text-[11px] text-slate-500">{event.competition}</p>
            <div>{event.recommendation ? <Badge variant={event.recommendation.status === "VALUE" ? "default" : "danger"}>{event.recommendation.status.replace("_", " ")}</Badge> : <Badge variant="neutral">Pending model</Badge>}</div>
            <div className="text-xs">{event.recommendation ? <><span className="number text-slate-200">{decimal(event.recommendation.best_odds)}</span><span className="number ml-2 text-emerald-300">+{percent(event.recommendation.edge)}</span></> : <span className="text-slate-700">—</span>}</div>
            <Button asChild variant="ghost" size="sm" className="w-fit"><Link href={`/events/${event.id}`} aria-label={`View ${event.name}`}><ArrowUpRight className="h-4 w-4" /></Link></Button>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <Card className="grid min-h-48 place-items-center p-8 text-center"><div><p className="text-sm font-semibold text-slate-300">{title}</p><p className="mt-2 max-w-md text-xs leading-relaxed text-slate-600">{detail}</p></div></Card>;
}

