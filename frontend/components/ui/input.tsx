import * as React from "react";

import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn("h-9 w-full rounded-md border border-border bg-slate-950/50 px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-emerald-400/50 focus:ring-2 focus:ring-emerald-400/10", className)} {...props} />;
}

