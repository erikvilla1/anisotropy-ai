"use client";

import { useEffect, useRef } from "react";
import { isActive } from "@/lib/studio-api";
import { buildValues, PLATE_TEST, type StudioForm } from "@/lib/studio-form";
import { LIVE_DEBOUNCE_MS, liveKey, setupComplete, shouldSolveLive } from "@/lib/studio-live";
import { plateValues, type PlateLists } from "@/lib/studio-plate";
import { isTow } from "@/lib/studio-tow";
import { remembered, RUN_BY_KEY } from "./local";
import type { CouponRun } from "./use-coupon-run";

/** Our kernel's answer kept current (ADR-0086): once the setup has every row it needs, each settled edit, on a panel or in the chat, asks for
 * a live solve after LIVE_DEBOUNCE_MS, the previous one aborted; a setup that loses a row drops the last answer, which no longer stands. Not
 * while a full run is going, and never for the fibre tow, which has no model. The page computes nothing: it sends the rows. */
export function useLiveSolve(apiBaseUrl: string, form: StudioForm, plate: PlateLists, run: CouponRun): void {
  const { solveLive, dropLive, liveFor, job } = run;
  const running = isActive(job?.state);
  const asked = useRef<string | null>(null); // the rows last sent, answered or not: never sent twice in a row
  useEffect(() => {
    const tow = isTow(form);
    const complete = setupComplete(form);
    if (!complete || tow) {
      if (liveFor !== null) dropLive();
      asked.current = null;
      return;
    }
    const rows = { ...form, filled_by: (form.filled_by ?? "").trim() || remembered(RUN_BY_KEY) }; // as the rail names the file when it solves
    const values = buildValues(rows, form.test === PLATE_TEST ? plateValues(plate) : undefined);
    const key = liveKey(values);
    if (!shouldSolveLive({ api: Boolean(apiBaseUrl), complete, running, tow, key, sent: asked.current === key ? key : liveFor })) return;
    const timer = window.setTimeout(() => { asked.current = key; void solveLive(values, key); }, LIVE_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [apiBaseUrl, form, plate, running, liveFor, solveLive, dropLive]);
}
