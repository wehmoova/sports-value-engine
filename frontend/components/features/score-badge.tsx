import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export function ScoreBadge({ label, value, compact = false }: { label: string; value: number; compact?: boolean }) {
  const variant = value >= 80 ? "default" : value >= 70 ? "blue" : value >= 60 ? "warning" : "danger";
  if (compact) return <Badge variant={variant}>{label} {value}</Badge>;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-500"><span>{label}</span><span className={cn("number font-semibold", value >= 80 ? "text-emerald-300" : value >= 70 ? "text-sky-300" : "text-amber-300")}>{value}/100</span></div>
      <Progress value={value} />
    </div>
  );
}

