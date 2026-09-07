import type { Metadata } from "next";

import { ChallengeSimulator } from "@/components/features/challenge-simulator";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Challenge Simulator" };

export default function ChallengePage() { return <div className="space-y-6"><PageHeader eyebrow="Paper trading only" title="Challenge simulator" description="Quantify required growth, target probability, ending-bankroll distribution and drawdown without changing the value engine or forcing high-risk selections." /><ChallengeSimulator /></div>; }

