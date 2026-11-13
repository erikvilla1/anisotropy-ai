"use client";
import { useEffect, useState } from "react";
import type { MaterialFeed } from "@/lib/material-evidence";

/** The revision monitor (services/material-monitor) runs only where a build turns it on with NEXT_PUBLIC_MATERIAL_MONITOR=on.
 * The hosted build leaves it unset: the page then fetches nothing and says the values are pinned to the cited edition. */
export const materialMonitorEnabled = process.env.NEXT_PUBLIC_MATERIAL_MONITOR === "on";

export function useMaterialFeed() {
  const [feed, setFeed] = useState<MaterialFeed | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    if (!materialMonitorEnabled) return;
    let active = true;
    let running = false;
    const controller = new AbortController();
    async function refresh() {
      if (running) return;
      running = true;
      try {
        const response = await fetch("/materials/catalog-status.json", { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]) });
        // No feed on this host: stop asking.
        if (response.status === 404) clearInterval(timer);
        if (!response.ok) throw new Error("Unavailable");
        const data = await response.json();
        if (data.schemaVersion !== 1 || !Number.isFinite(Date.parse(data.generatedAt)) || !Array.isArray(data.sources) || !Array.isArray(data.candidates) || !Array.isArray(data.releases)) throw new Error("Invalid feed");
        if (active) { setFeed(data); setUnavailable(false); }
      } catch { if (active) setUnavailable(true); }
      finally { running = false; }
    }
    const timer = setInterval(refresh, 30_000);
    void refresh();
    return () => { active = false; controller.abort(); clearInterval(timer); };
  }, []);
  if (!materialMonitorEnabled) return { feed: null, stale: false };
  const stale = unavailable || !feed || Date.now() - Date.parse(feed.generatedAt) > 180_000;
  return { feed, stale };
}
