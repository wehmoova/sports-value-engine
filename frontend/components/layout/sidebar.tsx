"use client";

import {
  Activity,
  BarChart3,
  CircleDollarSign,
  CircleOff,
  Database,
  Gauge,
  Menu,
  PanelsTopLeft,
  Settings,
  ShieldCheck,
  Target,
  Trophy,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const sections = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: PanelsTopLeft },
      { href: "/picks", label: "Today’s Picks", icon: Target },
      { href: "/odds", label: "Odds Movement", icon: Activity },
    ],
  },
  {
    label: "Sports",
    items: [
      { href: "/football", label: "Football", icon: Trophy },
      { href: "/tennis", label: "Tennis", icon: CircleDollarSign },
    ],
  },
  {
    label: "Betting",
    items: [
      { href: "/combinations", label: "Combinations", icon: Gauge },
      { href: "/avoid", label: "No Bet", icon: CircleOff },
    ],
  },
  {
    label: "Analytics",
    items: [
      { href: "/performance", label: "Performance", icon: BarChart3 },
      { href: "/bankroll", label: "Bankroll", icon: ShieldCheck },
      { href: "/challenge", label: "Challenge", icon: Gauge },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/system", label: "Data & Models", icon: Database },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {sections.map((section) => (
        <div key={section.label}>
          <p className="mb-1.5 px-3 text-[9px] font-bold uppercase tracking-[0.22em] text-slate-600">{section.label}</p>
          <div className="space-y-0.5">
            {section.items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <Link key={item.href} href={item.href} onClick={onNavigate} className={cn("flex h-9 items-center gap-3 rounded-md px-3 text-xs font-medium transition-colors", active ? "bg-emerald-400/10 text-emerald-300" : "text-slate-400 hover:bg-slate-900 hover:text-slate-100")}>
                  <Icon className="h-4 w-4" strokeWidth={1.7} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function Sidebar({ dataMode, dataHealth }: { dataMode: "real" | "simulation"; dataHealth: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="ghost" size="sm" className="fixed left-3 top-3 z-50 md:hidden" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></Button>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-border bg-[#080c13] md:flex">
        <Brand />
        <Navigation />
        <SidebarFooter dataMode={dataMode} dataHealth={dataHealth} />
      </aside>
      {open && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm md:hidden" onClick={() => setOpen(false)}>
          <aside className="flex h-full w-72 flex-col border-r border-border bg-[#080c13]" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center justify-between"><Brand /><Button variant="ghost" size="sm" aria-label="Close navigation" onClick={() => setOpen(false)}><X className="h-4 w-4" /></Button></div>
            <Navigation onNavigate={() => setOpen(false)} />
            <SidebarFooter dataMode={dataMode} dataHealth={dataHealth} />
          </aside>
        </div>
      )}
    </>
  );
}

function Brand() {
  return (
    <div className="flex h-[73px] items-center gap-3 border-b border-border px-5">
      <div className="grid h-8 w-8 place-items-center rounded-lg border border-emerald-300/20 bg-emerald-400/10 text-emerald-300"><Activity className="h-4 w-4" /></div>
      <div><p className="text-xs font-bold tracking-[0.14em] text-slate-100">SPORTS VALUE</p><p className="text-[9px] font-semibold tracking-[0.32em] text-emerald-400">ENGINE</p></div>
    </div>
  );
}

function SidebarFooter({ dataMode, dataHealth }: { dataMode: "real" | "simulation"; dataHealth: string }) {
  const real = dataMode === "real" && dataHealth === "HEALTHY";
  return (
    <div className="border-t border-border p-4">
      <div className={`flex items-center gap-2 text-[10px] ${real ? "text-emerald-300" : "text-amber-300"}`}><span className={`h-1.5 w-1.5 rounded-full ${real ? "bg-emerald-400" : "bg-amber-400"}`} />{dataHealth === "UNAVAILABLE" ? "DATA UNAVAILABLE" : dataMode.toUpperCase()}</div>
      <p className="mt-1 text-[9px] text-slate-600">Data health: {dataHealth.replaceAll("_", " ")}</p>
      <p className="mt-2 text-[9px] leading-relaxed text-slate-700">Pre-match analytics · No guaranteed returns</p>
    </div>
  );
}
