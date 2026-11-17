"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { importModel, StudioError, type Explanation, type Fields, type ImportedModel, type ModelUnits } from "@/lib/studio-api";
import { shownResults, type CouponRun } from "./use-coupon-run";
import type { PastState } from "./use-past-run";

/** A model brought in as a file (ADR-0105), beside the coupon the project sets up: while it is open the stage shows it and the assistant
 * answers from it; closing it returns to the coupon, whose rows it never touched. The page computes nothing: it sends the file and keeps
 * the answer, which lives in this page alone and is gone on a reload. */
export type ImportedState = {
  /** The import has the stage: its panel on the left, its model or its refusal in the centre. */
  open: boolean;
  /** A file is being read and solved. */
  busy: boolean;
  model: ImportedModel | null;
  /** A failure to reach or read the service, in words the page may show; a file the reader refused is `model.problem`. */
  problem: string;
  show(): void;
  close(): void;
  send(file: File, units: ModelUnits): Promise<void>;
};

export function useImportedModel(apiBaseUrl: string): ImportedState {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState<ImportedModel | null>(null);
  const [problem, setProblem] = useState("");
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort("unmount"), []);

  const show = useCallback(() => setOpen(true), []);
  const close = useCallback(() => {
    abort.current?.abort("closed"); abort.current = null;
    setOpen(false); setBusy(false); setModel(null); setProblem("");
  }, []);
  const send = useCallback(async (file: File, units: ModelUnits) => {
    if (!apiBaseUrl) return;
    abort.current?.abort("superseded");
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true); setProblem("");
    try {
      const answer = await importModel(apiBaseUrl, file, file.name, units, controller.signal);
      if (controller.signal.aborted) return;
      setModel(answer);
    } catch (error) {
      if (controller.signal.aborted) return;
      setModel(null);
      setProblem(error instanceof StudioError ? error.message : "The model could not be imported. Reload the page; if it happens again, contact us.");
    } finally {
      if (abort.current === controller) { abort.current = null; setBusy(false); }
    }
  }, [apiBaseUrl]);

  return useMemo(() => ({ open, busy, model, problem, show, close, send }), [open, busy, model, problem, show, close, send]);
}

/** What the stage shows and the assistant answers from: the imported model while it is open (ADR-0105), a past run while one is
 * (ADR-0109), else the coupon's results, the newer of the live answer and the full run's (`shownResults`). `live` marks a preview that a
 * full run would verify, which an imported model and a past run have none of. `readOnly` is either of the two: what is shown is read as
 * it stands, and no message changes it. */
export function resultsOnPage(run: Pick<CouponRun, "fields" | "live" | "liveAt" | "fieldsAt" | "explanation">, imported: Pick<ImportedState, "open" | "model">,
  past?: Pick<PastState, "open" | "fields" | "explanation">):
  { fields: Fields | null; live: boolean; explanation: Explanation | null; imported: boolean; past: boolean; readOnly: boolean } {
  if (imported.open) return { fields: imported.model?.fields ?? null, live: false, explanation: imported.model?.explanation ?? null, imported: true, past: false, readOnly: true };
  if (past?.open) return { fields: past.fields, live: false, explanation: past.explanation, imported: false, past: true, readOnly: true };
  const shown = shownResults(run);
  return { ...shown, explanation: shown.live ? run.live?.explanation ?? null : run.explanation, imported: false, past: false, readOnly: false };
}
