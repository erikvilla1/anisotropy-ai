"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { readVersions, setupKey, withResult, withRun, withVersion, writeVersions, type ModelVersion } from "@/lib/model-versions";
import { answerStat } from "@/lib/studio-answer";
import { printed } from "@/lib/studio-colors";
import type { StudioForm } from "@/lib/studio-form";
import type { PlateLists } from "@/lib/studio-plate";
import type { CouponRun } from "./use-coupon-run";

/** A change settles after this long without another: a value typed key by key is one version. */
export const SETTLE_MS = 1200;

export type VersionsState = {
  list: ModelVersion[];
  /** Says who makes the next change and why, before it is made: the assistant and the message it came from. */
  attribute(by: ModelVersion["by"], why: string | null): void;
  /** Goes back to a version: its rows and lists become the setup again, kept as a new version that says so. */
  restore(n: number): void;
};

/** The versions of the project's setup (ADR-0113), kept in this browser per project: a settled change adds one, a run marks the version it
 * was made from and its answer is kept there. Nothing here computes a number: a run's line is the package's values, printed. */
export function useVersions(project: string, form: StudioForm, plate: PlateLists, run: Pick<CouponRun, "job" | "fields" | "loadedJob">,
  setForm: (next: StudioForm) => void, setPlate: (next: PlateLists) => void, storage: () => Storage | null): VersionsState {
  const [list, setList] = useState<ModelVersion[]>([]);
  const loaded = useRef<string | null>(null);
  const next = useRef<{ by: ModelVersion["by"]; why: string | null; at: number } | null>(null);
  const setup = useRef({ form, plate });
  setup.current = { form, plate };

  // a project's versions come back with it; a project with none starts with the setup as it stands
  useEffect(() => {
    const kept = readVersions(storage(), project);
    loaded.current = project;
    setList(kept.length ? kept : withVersion([], setup.current.form, setup.current.plate, "you", null, new Date().toISOString()));
  }, [project]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (loaded.current === project && list.length) writeVersions(storage(), project, list); }, [list, project, storage]);

  const settle = useCallback(() => {
    // a word on who made the change holds for the change it was said for, not for one made long after
    const said = next.current && Date.now() - next.current.at < 5 * SETTLE_MS ? next.current : null;
    const by = said?.by ?? "you", why = said?.why ?? null;
    next.current = null;
    setList((l) => withVersion(l, setup.current.form, setup.current.plate, by, why, new Date().toISOString()));
  }, []);
  // a change becomes a version once it has settled
  const key = setupKey(form, plate);
  useEffect(() => {
    if (loaded.current !== project) return;
    const timer = setTimeout(settle, SETTLE_MS);
    return () => clearTimeout(timer);
  }, [key, project, settle]);

  // a run is made from the setup as it stands: settled at once, and marked
  const job = run.job?.job_id ?? null;
  useEffect(() => {
    if (!job) return;
    settle();
    setList((l) => withRun(l, job));
  }, [job, settle]);
  // its answer, once read, is kept on that version
  useEffect(() => {
    if (!run.loadedJob || !run.fields) return;
    const s = run.fields.summary, lab = run.fields.labels;
    const stat = answerStat(run.fields, printed);
    const result = { reaction: `${printed(Math.abs(s.reaction.value))} ${lab.force}`, displacement: `${printed(s.max_displacement.value)} ${lab.length}`,
      failure: stat ? `${stat.verdict}, R = ${stat.factor}` : "not checked" };
    const done = run.loadedJob;
    setList((l) => withResult(l, done, result));
  }, [run.loadedJob]); // eslint-disable-line react-hooks/exhaustive-deps

  const attribute = useCallback((by: ModelVersion["by"], why: string | null) => { next.current = { by, why, at: Date.now() }; }, []);
  const restore = useCallback((n: number) => {
    const version = list.find((v) => v.n === n);
    if (!version || setupKey(version.form, version.plate) === setupKey(setup.current.form, setup.current.plate)) return;
    next.current = { by: "you", why: `Back to version ${n}`, at: Date.now() };
    setForm(version.form);
    setPlate(version.plate);
  }, [list, setForm, setPlate]);
  return useMemo(() => ({ list, attribute, restore }), [list, attribute, restore]);
}
