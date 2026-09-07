import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Sidebar } from "@/components/layout/sidebar";
import { DataStatus } from "@/components/features/data-status";
import { apiFetch } from "@/lib/api";
import "./globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3001"),
  title: { default: "Sports Value Engine", template: "%s · Sports Value Engine" },
  description: "Transparent quantitative pre-match sports analytics, pricing and model monitoring.",
  openGraph: {
    title: "Sports Value Engine",
    description: "Probability. Price. Discipline.",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Sports Value Engine — Probability. Price. Discipline." }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Sports Value Engine",
    description: "Probability. Price. Discipline.",
    images: ["/og.png"],
  },
};

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  let mode: "real" | "simulation" = "real";
  let dataHealth = "UNAVAILABLE";
  try {
    const diagnostics = await apiFetch<{ data_mode: "real" | "simulation"; status: string }>("/system/data-diagnostics");
    mode = diagnostics.data_mode;
    dataHealth = diagnostics.status;
  } catch {
    // The shell remains usable while the backend starts; it never substitutes data.
  }
  return (
    <html lang="de" className="dark">
      <body>
        <Sidebar dataMode={mode} dataHealth={dataHealth} />
        <main className="data-grid min-h-screen md:pl-60">
          <div className="mx-auto min-h-screen max-w-[1600px] px-4 pb-16 pt-16 sm:px-6 md:pt-7 lg:px-8"><DataStatus />{children}</div>
        </main>
      </body>
    </html>
  );
}
