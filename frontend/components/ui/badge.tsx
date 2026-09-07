import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]",
  {
    variants: {
      variant: {
        default: "border-emerald-400/20 bg-emerald-400/10 text-emerald-300",
        neutral: "border-slate-500/20 bg-slate-500/10 text-slate-300",
        warning: "border-amber-400/20 bg-amber-400/10 text-amber-300",
        danger: "border-red-400/20 bg-red-400/10 text-red-300",
        blue: "border-sky-400/20 bg-sky-400/10 text-sky-300",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export function Badge({ className, variant, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

