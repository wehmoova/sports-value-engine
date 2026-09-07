import { KeyRound, SlidersHorizontal } from "lucide-react";
import type { Metadata } from "next";

import { SettingsForm, type SettingsValues } from "@/components/features/settings-form";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

export const metadata: Metadata = { title: "Settings" };
export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const settings = await apiFetch<SettingsValues>("/settings");
  return <div className="space-y-6"><PageHeader eyebrow="Decision policy" title="Value engine settings" description="Thresholds change which already-computed predictions qualify. They do not alter model probabilities or force additional recommendations." /><Card><CardHeader className="flex-row items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-lg bg-sky-400/10"><SlidersHorizontal className="h-4 w-4 text-sky-300" /></div><div><CardTitle>Qualification thresholds</CardTitle><p className="mt-1 text-xs text-slate-600">Single-user MVP settings persisted in the database</p></div></CardHeader><CardContent><SettingsForm initial={settings} /></CardContent></Card><Card className="border-amber-400/15"><CardContent className="flex gap-3 p-5"><KeyRound className="h-4 w-4 shrink-0 text-amber-300" /><div><p className="text-xs font-medium text-amber-100">Provider secrets stay server-side</p><p className="mt-1 text-[11px] leading-relaxed text-slate-500">API keys are configured through backend environment variables. They are never returned to this page or stored in browser state.</p></div></CardContent></Card></div>;
}

