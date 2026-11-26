"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Download } from "lucide-react";
import { askReport, fileUrl, getJob, MODEL_FILE_OPENING, POLL_MS, StudioError, type Fields, type JobStatus } from "@/lib/studio-api";
import { downloadable, downloadName, REPORT_WORDS, type ReportState } from "@/lib/studio-copy";

/** What a job's files are named after (ADR-0091): the standard and the layup the package wrote, else the rows on the page. */
export function namingOf(fields: Fields | null | undefined, form?: { standard?: string; test?: string; ply_1?: string } | null, layup?: string) {
  return {
    standard: fields?.summary.test_method?.designation ?? (form?.standard && form.standard !== "none" ? form.standard : null),
    test: fields?.coupon.test ?? form?.test ?? null,
    layup: fields?.coupon.layup ?? layup ?? null,
  };
}

/** How many times in a row the job may fail to be read while its report is written before the page says the report failed. */
const REPORT_RETRIES = 5;

/** A done run's report, written when someone asks for it (ADR-0064 amendment 3). `shown` is the job as last read here, which gains
 * its `document` once the report is written; `state` what the page says beside the button; `ask` starts it. A report asked for here
 * downloads when it is ready, through `save`; one found being written (asked for in another window) only gains its link. */
export function useReport(apiBase: string, job: JobStatus, save: (job: JobStatus) => void): {
  shown: JobStatus; state: ReportState; words: string; ask(): void;
} {
  const [own, setOwn] = useState<{ id: string; job: JobStatus | null; state: ReportState; words: string }>({ id: job.job_id, job: null, state: "idle", words: "" });
  const mine = own.id === job.job_id ? own : { id: job.job_id, job: null, state: "idle" as ReportState, words: "" };
  const shown = mine.job ?? job;
  const written = "document" in shown.outputs;
  const state: ReportState = written ? "idle" : mine.state === "idle" && shown.report === "writing" ? "writing" : mine.state;
  const asked = useRef<string | null>(null); // the job whose report was asked for here: it downloads when it is ready
  const misses = useRef(0);
  const id = job.job_id;

  const ask = useCallback(() => {
    asked.current = id;
    misses.current = 0;
    setOwn((before) => ({ id, job: before.id === id ? before.job : null, state: "writing", words: "" }));
    askReport(apiBase, id).then((answer) => {
      const ready = "document" in answer.outputs;
      setOwn({ id, job: answer, state: ready ? "idle" : "writing", words: "" });
      if (ready && asked.current === id) { asked.current = null; save(answer); }
    }).catch((error) => {
      // the API's own words when it refused in words fit to show (no report was kept; not finished yet); else what happened and what to do
      setOwn((before) => ({ id, job: before.id === id ? before.job : null, state: "failed", words: error instanceof StudioError ? error.message : "" }));
    });
  }, [apiBase, id, save]);

  useEffect(() => {
    if (state !== "writing" || !apiBase) return;
    const timer = window.setTimeout(async () => {
      try {
        const next = await getJob(apiBase, id);
        misses.current = 0;
        const ready = "document" in next.outputs;
        setOwn({ id, job: next, state: ready ? "idle" : next.report === "failed" ? "failed" : "writing", words: "" });
        if (ready && asked.current === id) { asked.current = null; save(next); }
      } catch {
        misses.current += 1;
        setOwn((before) => ({ id, job: before.id === id ? before.job : null, state: misses.current > REPORT_RETRIES ? "failed" : "writing", words: "" }));
      }
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [state, apiBase, id, own, save]);

  return { shown, state, words: mine.words || REPORT_WORDS[state], ask };
}

/** Hand a file to the browser to save, without leaving the page: a frame that is never shown loads the file's address, which the API
 * or the store answers as an attachment. An answer that is not a file stays in the frame, unseen; the link in the list still serves. */
function saveFile(url: string) {
  const frame = document.createElement("iframe");
  frame.hidden = true;
  frame.src = url;
  document.body.appendChild(frame);
  window.setTimeout(() => frame.remove(), 60_000);
}

/** A job's files with their plain labels and saved names, and the results in a window of their own. A customer is offered the report and
 * the solver input; `all`, the development switch's view, offers the full package and the reference solver's files too (decision D4,
 * ADR-0091 amendment 2). A run that wrote no PDF offers its report as a button: the PDF is written then, and downloads when it is ready
 * (ADR-0064 amendment 3). */
export function JobFiles({ apiBase, job, naming, viewer = true, testId, all = false }: {
  apiBase: string; job: JobStatus; naming: ReturnType<typeof namingOf>; viewer?: boolean; testId?: string; all?: boolean;
}) {
  const reportName = downloadName("document", naming);
  const save = useCallback((ready: JobStatus) => saveFile(fileUrl(apiBase, ready.job_id, "document", reportName)), [apiBase, reportName]);
  const report = useReport(apiBase, job, save);
  const shown = report.shown;
  const available = downloadable(shown, all); // none while the run is going: its files are still being written and stored
  if (!available.length) return null;
  return (
    <ul className="studio-downloads" data-testid={testId}>
      {available.map(([key, label]) => {
        const name = downloadName(key, naming);
        if (key === "document" && !("document" in shown.outputs)) {
          return (
            <li key={key}>
              <button type="button" className="studio-download-ask" data-key={key} data-state={report.state} disabled={report.state === "writing"}
                aria-busy={report.state === "writing"} onClick={report.ask}>
                <Download size={13} aria-hidden="true" /> {label}
              </button>
              <span className={report.state === "failed" ? "studio-download-note studio-problem" : "studio-download-note"} role="status" data-testid="report-note">{report.words}</span>
            </li>
          );
        }
        return (
          <li key={key}>
            <a href={fileUrl(apiBase, shown.job_id, key, name)} download={name} target="_blank" rel="noreferrer" data-key={key}><Download size={13} aria-hidden="true" /> {label}</a>
            {key === "abaqus_deck" ? <span className="studio-download-note" data-testid="abaqus-file-opening">{MODEL_FILE_OPENING.abaqus}</span> : null}
          </li>
        );
      })}
      {viewer ? (
        <li><a href={`/workspace/fea/view?job=${encodeURIComponent(shown.job_id)}`} target="_blank" rel="noreferrer"><ArrowUpRight size={13} aria-hidden="true" /> Open results in a new window</a></li>
      ) : null}
    </ul>
  );
}
