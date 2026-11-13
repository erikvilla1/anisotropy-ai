"use client";

import { Download, ExternalLink } from "lucide-react";
import { DOWNLOADS, fileUrl, type Fields, type JobStatus } from "@/lib/studio-api";
import { downloadName } from "@/lib/studio-copy";

/** What a job's files are named after (ADR-0091): the standard and the layup the package wrote, else the rows on the page. */
export function namingOf(fields: Fields | null | undefined, form?: { standard?: string; test?: string; ply_1?: string } | null, layup?: string) {
  return {
    standard: fields?.summary.test_method?.designation ?? (form?.standard && form.standard !== "none" ? form.standard : null),
    test: fields?.coupon.test ?? form?.test ?? null,
    layup: fields?.coupon.layup ?? layup ?? null,
  };
}

/** A job's files with their plain labels and saved names, and the results in a window of their own. */
export function JobFiles({ apiBase, job, naming, viewer = true, testId }: {
  apiBase: string; job: JobStatus; naming: ReturnType<typeof namingOf>; viewer?: boolean; testId?: string;
}) {
  const available = DOWNLOADS.filter(([key]) => key in job.outputs);
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
        <li><a href={`/workspace/fea/view?job=${encodeURIComponent(job.job_id)}`} target="_blank" rel="noreferrer"><ExternalLink size={13} aria-hidden="true" /> Open results in a new window</a></li>
      ) : null}
    </ul>
  );
}
