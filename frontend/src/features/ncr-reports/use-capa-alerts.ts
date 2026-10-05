"use client";

import { useEffect, useState } from "react";

import { getCapaAlerts } from "./api";
import type { CapaAlerts } from "./types";

// What needs the current user's attention (QUAL-CAPA-001), shared by the sidebar badge and the corrective actions page.
// Kept for a minute so moving between pages does not ask again; refreshCapaAlerts() after a change.
const TTL = 60_000;
let cached: { at: number; value: CapaAlerts } | null = null;
let pending: Promise<CapaAlerts | null> | null = null;
const listeners = new Set<(value: CapaAlerts | null) => void>();

function load(force = false): Promise<CapaAlerts | null> {
  if (!force && cached && Date.now() - cached.at < TTL) return Promise.resolve(cached.value);
  if (!force && pending) return pending;
  pending = getCapaAlerts()
    .then(value => (value && typeof value.total === "number" ? value : null))
    .catch(() => null)
    .then(value => {
      pending = null;
      cached = value ? { at: Date.now(), value } : null;
      listeners.forEach(listener => listener(value));
      return value;
    });
  return pending;
}

export function refreshCapaAlerts() {
  return load(true);
}

export function resetCapaAlerts() {
  cached = null;
  pending = null;
}

export function useCapaAlerts(enabled: boolean): CapaAlerts | null {
  const [value, setValue] = useState<CapaAlerts | null>(enabled && cached ? cached.value : null);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const listener = (next: CapaAlerts | null) => { if (active) setValue(next); };
    listeners.add(listener);
    void load().then(listener);
    return () => { active = false; listeners.delete(listener); };
  }, [enabled]);
  return enabled ? value : null;
}
