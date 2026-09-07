"use client";

import { Save } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

import { clientApiUrl } from "@/lib/client-api";
const schema = z.object({ min_odds: z.number().gt(1).max(20), min_edge: z.number().min(0).max(0.5), min_ev: z.number().min(0).max(2), min_confidence: z.number().int().min(0).max(100), timezone: z.string().min(1), odds_format: z.enum(["DECIMAL", "AMERICAN", "FRACTIONAL"]), sports_enabled: z.array(z.string()), notifications_enabled: z.boolean(), auto_refresh_minutes: z.number().int().min(5).max(1440) });
export type SettingsValues = z.infer<typeof schema>;

export function SettingsForm({ initial }: { initial: SettingsValues }) {
  const [values, setValues] = useState(initial);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const updateNumber = (key: keyof SettingsValues) => (event: React.ChangeEvent<HTMLInputElement>) => setValues((current) => ({ ...current, [key]: Number(event.target.value) }));
  async function save(event: React.FormEvent) {
    event.preventDefault();
    const checked = schema.safeParse(values);
    if (!checked.success) { setState("error"); return; }
    setState("saving");
    try {
      const response = await fetch(`${clientApiUrl()}/api/v1/settings`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(checked.data) });
      if (!response.ok) throw new Error("Save failed");
      setState("saved");
    } catch { setState("error"); }
  }
  return <form onSubmit={save} className="space-y-6"><div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4"><Field label="Minimum odds" hint="Reject short standalone prices"><Input type="number" min="1.01" max="20" step="0.01" value={values.min_odds} onChange={updateNumber("min_odds")} /></Field><Field label="Minimum edge" hint="Probability points as decimal"><Input type="number" min="0" max="0.5" step="0.01" value={values.min_edge} onChange={updateNumber("min_edge")} /></Field><Field label="Minimum EV" hint="Expected value as decimal"><Input type="number" min="0" max="2" step="0.01" value={values.min_ev} onChange={updateNumber("min_ev")} /></Field><Field label="Minimum confidence" hint="Deterministic score 0–100"><Input type="number" min="0" max="100" step="1" value={values.min_confidence} onChange={updateNumber("min_confidence")} /></Field><Field label="Timezone" hint="Display and scheduler context"><Input value={values.timezone} onChange={(event) => setValues((current) => ({ ...current, timezone: event.target.value }))} /></Field><Field label="Odds format" hint="UI presentation only"><Select className="w-full" value={values.odds_format} onChange={(event) => setValues((current) => ({ ...current, odds_format: event.target.value as SettingsValues["odds_format"] }))}><option value="DECIMAL">Decimal</option><option value="AMERICAN">American</option><option value="FRACTIONAL">Fractional</option></Select></Field><Field label="Auto refresh" hint="Minimum five minutes"><Input type="number" min="5" max="1440" step="5" value={values.auto_refresh_minutes} onChange={updateNumber("auto_refresh_minutes")} /></Field></div><div className="flex items-center gap-3"><Button type="submit" disabled={state === "saving"}><Save className="h-3.5 w-3.5" />{state === "saving" ? "Saving…" : "Save settings"}</Button>{state !== "idle" && <p className={`text-[10px] ${state === "error" ? "text-red-300" : "text-slate-500"}`}>{state === "saved" ? "Settings saved." : state === "error" ? "Check the values and API connection." : ""}</p>}</div></form>;
}

function Field({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) { return <label className="space-y-2"><span className="block text-xs font-medium text-slate-300">{label}</span>{children}<span className="block text-[10px] text-slate-600">{hint}</span></label>; }
