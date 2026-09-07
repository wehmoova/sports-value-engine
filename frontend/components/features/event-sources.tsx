import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { compactTime, decimal } from "@/lib/utils";
import type { EventDetail } from "@/types";

export function EventSources({ event }: { event: EventDetail }) {
  return <Card><CardHeader><CardTitle>Data sources & observed odds</CardTitle><p className="text-xs text-slate-500">Event: {event.data_sources?.event ?? "Unknown"} · Fetched {compactTime(event.data_sources?.fetched_at ?? null)}</p></CardHeader><CardContent>
    {event.statistics_sources?.map((source, index) => <p className="mb-3 text-xs text-slate-500" key={index}>Statistics: {source.provider} · {source.side} · Fetched {compactTime(source.fetched_at)} · Sample {source.sample_size}</p>)}
    {!event.odds.length ? <p className="text-xs text-slate-500">No timestamped provider odds available.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr>{["Provider / bookmaker", "Market / selection", "Price", "Observed", "Validation"].map(label => <th key={label} className="pb-3 pr-4 text-slate-600">{label}</th>)}</tr></thead><tbody>{event.odds.map((odd, index) => <tr key={index} className="border-t border-border"><td className="py-3 pr-4">{odd.provider} / {odd.bookmaker}</td><td>{odd.market} / {odd.selection}{odd.point != null ? ` (${odd.point})` : ""}</td><td>{decimal(odd.decimal_odds)}</td><td>{compactTime(odd.observed_at)}</td><td>{odd.validation_status} · {odd.freshness_status}</td></tr>)}</tbody></table></div>}
  </CardContent></Card>;
}
