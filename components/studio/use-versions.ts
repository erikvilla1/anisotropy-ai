"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { mergeVersions, readServerVersions, readVersions, runsToSend, setupKey, unsent, versionUpload, withResult, withRun, withVersion, writeVersions,
  type ModelVersion } from "@/lib/model-versions";
import { isUuid } from "@/lib/project-store";
import { addVersion, listVersions, markVersionRun, noProjectStore, StudioError } from "@/lib/studio-api";
import { answerStat } from "@/lib/studio-answer";
import { printed } from "@/lib/studio-colors";
import type { StudioForm } from "@/lib/studio-form";
import type { PlateLists } from "@/lib/studio-plate";
import type { CouponRun } from "./use-coupon-run";

/** A change settles after this long without another: a value typed key by key is one version. */
export const SETTLE_MS = 1200;
/** A new project reaches the server a moment after it is made (`SYNC_MS` in project-sync.ts); a version sent before it is tried again
 * this long after, a few times. */
const RETRY_MS = 3000;
const RETRIES = 5;

export type VersionsState = {
  list: ModelVersion[];
  /** Says who makes the next change and why, before it is made: the assistant and the message it came from. */
  attribute(by: ModelVersion["by"], why: string | null): void;
  /** Goes back to a version: its rows and lists become the setup again, kept as a new version that says so. */
  restore(n: number): void;
};

/** The versions of the project's setup (ADR-0113): a settled change adds one, a run marks the version it was made from and its answer is
 * kept there. Since ADR-0143 the server keeps them with the project, so the history follows the engineer to another browser and a change
 * the workspace's tools make is in it; this browser keeps a copy and shows it at once, and keeps the versions alone where the API keeps no
 * projects (`noProjectStore`) or cannot be reached. Nothing here computes a number: a run's line is the package's values, printed. */
export function useVersions(apiBaseUrl: string, project: string, form: StudioForm, plate: PlateLists,
  run: Pick<CouponRun, "job" | "fields" | "loadedJob" | "clearChecked" | "clearResults">, setForm: (next: StudioForm) => void,
  setPlate: (next: PlateLists) => void, storage: () => Storage | null): VersionsState {
  const [list, setList] = useState<ModelVersion[]>([]);
  const loaded = useRef<string | null>(null);
  const next = useRef<{ by: ModelVersion["by"]; why: string | null; at: number } | null>(null);
  const setup = useRef({ form, plate });
  setup.current = { form, plate };
  const shown = useRef<ModelVersion[]>([]);
  shown.current = list;
  // the server's side: its versions as last heard, whether it keeps none (off), and one sending at a time
  const server = useRef<{ project: string; list: ModelVersion[] | null; off: boolean; busy: boolean; again: boolean; tries: number }>(
    { project: "", list: null, off: false, busy: false, again: false, tries: 0 });
  const api = useRef(apiBaseUrl);
  api.current = apiBaseUrl;

  /** What this browser holds that the server does not, sent in order: the versions after the server's last, then the runs marked. */
  const flush = useCallback(async () => {
    const s = server.current;
    if (!api.current || s.off || s.list === null || !isUuid(s.project)) return;
    if (s.busy) { s.again = true; return; }
    s.busy = true;
    const id = s.project;
    try {
      let held = s.list, sent = 0;
      for (const v of unsent(shown.current, held)) {
        sent += 1;
        const kept = readServerVersions([await addVersion(api.current, id, versionUpload(v))]);
        if (server.current.project !== id) return;
        held = kept.length && kept[0].n > (held[held.length - 1]?.n ?? 0) ? [...held, kept[0]] : held;
      }
      s.list = held;
      const merged = mergeVersions(held, shown.current);
      for (const mark of runsToSend(held, merged)) {
        sent += 1;
        const marked = readServerVersions([await markVersionRun(api.current, id, mark.n, { job: mark.job, result: mark.result })]);
        if (server.current.project !== id) return;
        if (marked.length) s.list = s.list.map((v) => (v.n === marked[0].n ? marked[0] : v));
      }
      s.tries = 0;
      // only what the server answered changes the list: a list set anew each time would send again, without end
      if (sent) setList((current) => mergeVersions(s.list ?? [], current));
    } catch (error) {
      if (noProjectStore(error)) { s.off = true; return; }
      // a project the server does not hold yet is sent a moment after it is made: try again, a few times
      if (error instanceof StudioError && error.status === 404 && s.tries < RETRIES) {
        s.tries += 1;
        window.setTimeout(() => void flush(), RETRY_MS);
      }
    } finally {
      s.busy = false;
      if (s.again) { s.again = false; void flush(); }
    }
  }, []);

  // a project's versions come back with it: this browser's copy at once, then the server's, which hold the changes made elsewhere
  useEffect(() => {
    const kept = readVersions(storage(), project);
    loaded.current = project;
    server.current = { project, list: null, off: false, busy: false, again: false, tries: 0 };
    setList(kept.length ? kept : withVersion([], setup.current.form, setup.current.plate, "you", null, new Date().toISOString()));
    if (!apiBaseUrl || !isUuid(project)) return;
    const controller = new AbortController();
    listVersions(apiBaseUrl, project, controller.signal).then((payload) => {
      if (server.current.project !== project) return;
      server.current.list = readServerVersions(payload);
      setList((current) => mergeVersions(server.current.list ?? [], current));
      void flush();
    }).catch((error) => {
      if (noProjectStore(error)) server.current.off = true;
      // a project the server does not hold yet has no versions there: they are sent once it is saved
      else if (error instanceof StudioError && error.status === 404 && server.current.project === project) {
        server.current.list = [];
        window.setTimeout(() => void flush(), RETRY_MS);
      }
    });
    return () => controller.abort("replaced");
  }, [project, apiBaseUrl]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (loaded.current !== project || !list.length) return;
    writeVersions(storage(), project, list);
    void flush();
  }, [list, project, storage, flush]);

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

  // a change still settling is kept as it stands first, so the engineer's typing is never put down to the assistant's message
  const attribute = useCallback((by: ModelVersion["by"], why: string | null) => { settle(); next.current = { by, why, at: Date.now() }; }, [settle]);
  const restore = useCallback((n: number) => {
    const version = list.find((v) => v.n === n);
    if (!version || setupKey(version.form, version.plate) === setupKey(setup.current.form, setup.current.plate)) return;
    settle();
    next.current = { by: "you", why: `Back to version ${n}`, at: Date.now() };
    setForm(version.form);
    setPlate(version.plate);
    run.clearChecked(); // the check and the results shown were of another setup; the live solve answers this one again
    run.clearResults();
  }, [list, setForm, setPlate, settle, run]);
  return useMemo(() => ({ list, attribute, restore }), [list, attribute, restore]);
}
