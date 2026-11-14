"use client";

import { ArrowUpRight, Download } from "lucide-react";
import { fileUrl, type Fields, type JobStatus } from "@/lib/studio-api";
import { downloadName, downloadsFor } from "@/lib/studio-copy";

/** What a job's files are named after (ADR-0091): the standard and the layup the package wrote, else the rows on the page. */
export function namingOf(fields: Fields | null | undefined, form?: { standard?: string; test?: string; ply_1?: string } | null, layup?: string) {
  return {
    standard: fields?.summary.test_method?.designation ?? (form?.standard && form.standard !== "none" ? form.standard : null),
    test: fields?.coupon.test ?? form?.test ?? null,
    layup: fields?.coupon.layup ?? layup ?? null,
  };
}

/** A job's files with their plain labels and saved names, and the results in a window of their own. A customer is offered the report and
 * the solver input; `all`, the development switch's view, offers the full package and the reference solver's files too (decision D4,
 * ADR-0091 amendment 2). */
export function JobFiles({ apiBase, job, naming, viewer = true, testId, all = false }: {
  apiBase: string; job: JobStatus; naming: ReturnType<typeof namingOf>; viewer?: boolean; testId?: string; all?: boolean;
}) {
  const available = downloadsFor(all).filter(([key]) => key in job.outputs);
  if (!available.length) return null;
  return (
    <ul className="studio-downloads" data-testid={testId}>
      {available.map(([key, label]) => {
        const name = downloadName(key, naming);
        return (
          <li key={key}>
            <a href={fileUrl(apiBase, job.job_id, key, name)} download={name} target="_blank" rel="noreferrer" data-key={key}><Download size={13} aria-hidden="true" /> {label}</a>
          </li>
        );
      })}
      {viewer ? (
        <li><a href={`/workspace/fea/view?job=${encodeURIComponent(job.job_id)}`} target="_blank" rel="noreferrer"><ArrowUpRight size={13} aria-hidden="true" /> Open results in a new window</a></li>
      ) : null}
    </ul>
  );
}
