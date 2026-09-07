import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function EventNotFound() { return <div className="grid min-h-[70vh] place-items-center text-center"><div><p className="text-[10px] uppercase tracking-[.2em] text-red-300">404 · Event</p><h1 className="mt-3 text-2xl font-semibold">Event not found</h1><p className="mt-2 text-sm text-slate-600">The event may have expired or its provider mapping changed.</p><Button asChild variant="outline" className="mt-5"><Link href="/dashboard">Return to dashboard</Link></Button></div></div>; }

