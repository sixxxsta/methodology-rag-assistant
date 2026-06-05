"use client";

import { useCallback, useEffect, useState } from "react";
import { getCycleId, setCycleId as persistCycleId } from "./auth";
import { fetchCycles } from "./api";

export function notifyCycleChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("edagent-cycle-changed"));
  }
}

export function useActiveCycleId(): number | null {
  const [cycleId, setCycleIdState] = useState<number | null>(() => getCycleId());

  useEffect(() => {
    const sync = () => setCycleIdState(getCycleId());
    window.addEventListener("edagent-cycle-changed", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("edagent-cycle-changed", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return cycleId;
}

export function useCycleLabel(cycleId: number | null): string | null {
  const [label, setLabel] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!cycleId) {
      setLabel(null);
      return;
    }
    try {
      const { cycles } = await fetchCycles();
      const c = cycles.find((x) => x.id === cycleId);
      setLabel(c ? c.name : `Цикл #${cycleId}`);
    } catch {
      setLabel(`Цикл #${cycleId}`);
    }
  }, [cycleId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onChange = () => load();
    window.addEventListener("edagent-cycle-changed", onChange);
    return () => window.removeEventListener("edagent-cycle-changed", onChange);
  }, [load]);

  return label;
}

export function saveActiveCycleId(id: number) {
  persistCycleId(id);
  notifyCycleChanged();
}
