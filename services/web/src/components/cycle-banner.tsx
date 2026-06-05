"use client";

import Link from "next/link";
import { useActiveCycleId, useCycleLabel } from "@/lib/use-cycle";

export function CycleBanner() {
  const cycleId = useActiveCycleId();
  const label = useCycleLabel(cycleId);

  if (!cycleId || !label) return null;

  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accent/30 bg-accent/10 px-4 py-3">
      <p className="text-sm text-text">
        <span className="text-muted">Активный цикл:</span>{" "}
        <span className="font-semibold text-accent">{label}</span>
        <span className="ml-2 text-xs text-muted">(данные фаз только этого цикла)</span>
      </p>
      <Link
        href="/dashboard"
        className="text-xs text-accent hover:underline"
      >
        Сменить цикл
      </Link>
    </div>
  );
}
