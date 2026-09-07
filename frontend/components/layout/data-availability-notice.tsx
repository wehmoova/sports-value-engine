import { DatabaseZap } from "lucide-react";

export function DataAvailabilityNotice({ configured }: { configured: boolean }) {
  if (configured) return null;
  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-4 py-3 text-xs text-amber-100/75">
      <DatabaseZap className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
      <p><span className="font-semibold text-amber-200">Real data provider not configured.</span> Add server-side provider credentials, then run a real-data sync. No demo events, predictions or picks are substituted.</p>
    </div>
  );
}
