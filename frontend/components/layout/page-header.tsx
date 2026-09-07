import { Clock3 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { compactTime } from "@/lib/utils";

export function PageHeader({ eyebrow, title, description, updatedAt }: { eyebrow: string; title: string; description: string; updatedAt?: string | null }) {
  return (
    <header className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div><p className="mb-2 text-[10px] font-bold uppercase tracking-[0.24em] text-emerald-400">{eyebrow}</p><h1 className="text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">{title}</h1><p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">{description}</p></div>
      {updatedAt && <Badge variant="neutral" className="w-fit gap-1.5 normal-case tracking-normal"><Clock3 className="h-3 w-3" />Updated {compactTime(updatedAt)}</Badge>}
    </header>
  );
}

