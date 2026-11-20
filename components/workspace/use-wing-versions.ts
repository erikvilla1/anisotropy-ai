"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { WingDescription } from "@/lib/wing";
import { readWingVersions, wingKey, withWingCheck, withWingCheckResult, withWingVersion, writeWingVersions, type WingVersion } from "@/lib/wing-versions";
import { browserStorage } from "@/components/studio/project-context";

/** A change settles after this long without another: a value typed key by key is one version (as ADR-0113's SETTLE_MS). */
export const WING_SETTLE_VERSION_MS = 1200;

export type WingVersions = {
  list: WingVersion[];
  /** Says who makes the next change and why, before it is made: the assistant and the message it came from. */
  attribute(by: WingVersion["by"], why: string | null): void;
  /** Goes back to a version: its description becomes the wing again, kept as a new version that says so. */
  restore(n: number): void;
  /** A finite element check was started from the wing as it stands, or came back with its headline. */
  checked(job: string, headline?: string | null): void;
};

/** The versions of a wing (ADR-0122), kept in this browser per project: a settled change adds one, a check marks the version it was
 * started from. `active` is false until the page has a wing project to keep (a page opened on nothing keeps nothing until it changes). */
export function useWingVersions(project: string, active: boolean, wing: WingDescription, replace: (wing: WingDescription) => void): WingVersions {
  const [list, setList] = useState<WingVersion[]>([]);
  const loaded = useRef<string | null>(null);
  const next = useRef<{ by: WingVersion["by"]; why: string | null; at: number } | null>(null);
  const current = useRef(wing);
  current.current = wing;

  // a wing's versions come back with it; a wing with none starts with the description as it stands
  useEffect(() => {
    if (!active || loaded.current === project) return;
    const kept = readWingVersions(browserStorage(), project);
    loaded.current = project;
    setList(kept.length ? kept : withWingVersion([], current.current, "you", null, new Date().toISOString()));
  }, [project, active]);
  useEffect(() => { if (loaded.current === project && list.length) writeWingVersions(browserStorage(), project, list); }, [list, project]);

  const settle = useCallback(() => {
    // a word on who made the change holds for the change it was said for, not for one made long after
    const said = next.current && Date.now() - next.current.at < 5 * WING_SETTLE_VERSION_MS ? next.current : null;
    next.current = null;
    setList((l) => (l.length ? withWingVersion(l, current.current, said?.by ?? "you", said?.why ?? null, new Date().toISOString()) : l));
  }, []);
  const key = wingKey(wing);
  useEffect(() => {
    if (loaded.current !== project) return;
    const timer = setTimeout(settle, WING_SETTLE_VERSION_MS);
    return () => clearTimeout(timer);
  }, [key, project, settle]);

  // a change still settling is kept as it stands first, so the engineer's typing is never put down to the assistant's message
  const attribute = useCallback((by: WingVersion["by"], why: string | null) => { settle(); next.current = { by, why, at: Date.now() }; }, [settle]);
  const restore = useCallback((n: number) => {
    const version = list.find((v) => v.n === n);
    if (!version || wingKey(version.wing) === wingKey(current.current)) return;
    settle();
    next.current = { by: "you", why: `Back to version ${n}`, at: Date.now() };
    replace(version.wing);
  }, [list, replace, settle]);
  const checked = useCallback((job: string, headline?: string | null) => {
    if (headline) { setList((l) => withWingCheckResult(l, job, headline)); return; }
    settle(); // the check is of the wing as it stands
    setList((l) => withWingCheck(l, job));
  }, [settle]);
  return useMemo(() => ({ list, attribute, restore, checked }), [list, attribute, restore, checked]);
}
