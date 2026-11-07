"use client";

import { useCallback, useEffect, useRef } from "react";
import { isUuid, projectOfRecord, uploadOf, type Project } from "@/lib/project-store";
import { listProjects, noProjectStore, putProject, type ProjectUpload } from "@/lib/studio-api";

export const SYNC_MS = 1500;

type Pending = { id: string; upload: ProjectUpload; payload: string };

/** Keeps a project on the server (ADR-0062, part 6): a moment after each change, the project as the page states it is PUT by its id,
 * under the signed-in email behind Access or the actor locally; what is still unsent when the page is left goes at once. With run
 * records off the API has no project store (503) and the browser keeps the project alone, as before; any other failure is tried again
 * on the next change. */
export function useProjectSync(apiBaseUrl: string, project: Project): void {
  const sent = useRef("");
  const off = useRef(false);
  const pending = useRef<Pending | null>(null);
  const api = useRef(apiBaseUrl);
  useEffect(() => { api.current = apiBaseUrl; }, [apiBaseUrl]);

  const send = useCallback(async (item: Pending) => {
    if (!api.current || off.current) return;
    try {
      await putProject(api.current, item.id, item.upload);
      sent.current = item.payload;
      if (pending.current === item) pending.current = null;
    } catch (error) {
      if (noProjectStore(error)) off.current = true;
    }
  }, []);

  useEffect(() => {
    if (!apiBaseUrl || off.current || !isUuid(project.id)) return;
    const upload = uploadOf(project);
    const payload = JSON.stringify(upload);
    if (payload === sent.current) { pending.current = null; return; }
    const item: Pending = { id: project.id, upload, payload };
    pending.current = item;
    const timer = window.setTimeout(() => void send(item), SYNC_MS);
    return () => window.clearTimeout(timer);
  }, [apiBaseUrl, project, send]);

  // leaving the page: what is still unsent goes now
  useEffect(() => () => { const item = pending.current; if (item) void send(item); }, [send]);
}

/** For a browser that holds no project of the kind: the newest one on the server, fetched once and handed over; nothing when there is
 * none, when the API keeps no projects, or when the engineer has already started typing. */
export function useNewestFromServer(apiBaseUrl: string, kind: Project["kind"], wanted: boolean, onFound: (project: Project) => void): void {
  const asked = useRef(false);
  useEffect(() => {
    if (!apiBaseUrl || !wanted || asked.current) return;
    asked.current = true;
    const controller = new AbortController();
    listProjects(apiBaseUrl, controller.signal).then((records) => {
      const found = records.map(projectOfRecord).find((p): p is Project => p !== null && p.kind === kind);
      if (found) onFound(found);
    }).catch(() => { /* no store, or no answer: the browser's project stands */ });
    return () => controller.abort("replaced");
  }, [apiBaseUrl, kind, wanted]); // eslint-disable-line react-hooks/exhaustive-deps
}
