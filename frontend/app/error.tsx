"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <div className="grid min-h-[70vh] place-items-center"><div className="max-w-md rounded-xl border border-red-400/20 bg-red-400/[0.04] p-8 text-center"><AlertTriangle className="mx-auto h-7 w-7 text-red-300" /><h2 className="mt-4 text-lg font-semibold">Analytics API unavailable</h2><p className="mt-2 text-sm text-slate-500">The page could not load persisted analytics. Confirm the backend and database are healthy, then retry.</p><Button variant="outline" className="mt-5" onClick={reset}><RotateCcw className="h-3.5 w-3.5" />Retry</Button></div></div>;
}

