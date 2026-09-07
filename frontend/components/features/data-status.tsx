import { apiFetch } from "@/lib/api";
import { compactTime } from "@/lib/utils";

export async function DataStatus() {
  let data: { bot_status: string; data_mode: string; last_sync: string | null; last_analysis: string | null };
  try {
    data = await apiFetch("/system/health");
  } catch {
    data = { bot_status: "UNAVAILABLE", data_mode: "UNKNOWN", last_sync: null, last_analysis: null };
  }
  return <div className="mb-6 grid grid-cols-2 gap-3 border-b border-border pb-4 text-[10px] sm:grid-cols-4">
    {[["BOT STATUS", data.bot_status.replaceAll("_", " ")], ["DATA MODE", data.data_mode.toUpperCase()], ["LAST SYNC", compactTime(data.last_sync)], ["LAST ANALYSIS", compactTime(data.last_analysis)]].map(([label, value]) => <div key={label}><p className="text-slate-600">{label}</p><p className="mt-1 text-slate-300">{value}</p></div>)}
  </div>;
}
