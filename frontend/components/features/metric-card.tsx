import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function MetricCard({ label, value, detail, icon: Icon, positive = false }: { label: string; value: string | number; detail?: string; icon: LucideIcon; positive?: boolean }) {
  return (
    <Card className="relative overflow-hidden">
      <div className={cn("absolute inset-x-0 top-0 h-px", positive ? "bg-gradient-to-r from-transparent via-emerald-400/60 to-transparent" : "bg-gradient-to-r from-transparent via-slate-500/30 to-transparent")} />
      <CardContent className="p-4">
        <div className="flex items-center justify-between"><p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">{label}</p><Icon className={cn("h-4 w-4", positive ? "text-emerald-400" : "text-slate-600")} /></div>
        <p className={cn("number mt-4 text-2xl font-semibold tracking-tight", positive ? "text-emerald-300" : "text-slate-100")}>{value}</p>
        {detail && <p className="mt-1 text-[10px] text-slate-600">{detail}</p>}
      </CardContent>
    </Card>
  );
}

