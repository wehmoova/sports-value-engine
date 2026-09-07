import * as React from "react";

import { cn } from "@/lib/utils";

export function Select({ className, children, ...props }: React.ComponentProps<"select">) {
  return <select className={cn("h-9 rounded-md border border-border bg-slate-950/70 px-3 text-xs text-foreground outline-none focus:border-emerald-400/50", className)} {...props}>{children}</select>;
}

