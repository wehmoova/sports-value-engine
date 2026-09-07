"use client";

import { Play, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

import { clientApiUrl } from "@/lib/client-api";

export function RunAnalysisButton() {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const run = useCallback(async () => {
    setState("running");
    try {
      const response = await fetch(`${clientApiUrl()}/api/v1/admin/sync-real-data`, { method: "POST" });
      const payload = (await response.json()) as { id?: string; status?: string; message?: string };
      if (!response.ok) throw new Error(payload.message ?? "Analysis could not start");
      setMessage(payload.message ?? "Analysis queued.");
      setState("done");
      setTimeout(() => router.refresh(), 800);
      return { id: payload.id, status: payload.status, message: payload.message };
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Analysis could not start");
      setState("error");
      throw error;
    }
  }, [router]);

  useEffect(() => {
    const context = document.modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    void Promise.resolve(context.registerTool({
      name: "start_sports_analysis",
      title: "Run sports analysis",
      description: "Start the existing provider ingestion and pre-match analysis job, unless another run is active.",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
      annotations: { readOnlyHint: false, untrustedContentHint: false },
      async execute(input) {
        if (typeof input !== "object" || input === null || Object.keys(input).length !== 0) throw new Error("This action accepts an empty object only.");
        return await run();
      },
    }, { signal: lifecycle.signal })).catch(() => undefined);
    return () => lifecycle.abort();
  }, [run]);

  return <div className="flex flex-wrap items-center gap-3"><Button onClick={() => void run()} disabled={state === "running"}>{state === "running" ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}{state === "running" ? "Starting…" : "Run analysis now"}</Button>{message && <p className={`text-[10px] ${state === "error" ? "text-red-300" : "text-slate-500"}`}>{message}</p>}</div>;
}
