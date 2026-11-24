"use client";

import { useEffect, useState } from "react";
import { qaItems, qaLine, type QARecord } from "@/lib/qa";
import { getQARecord } from "@/lib/studio-api";

/** A done run's quality checks in one line, with the checks folded under it (ADR-0137): read once from the run's QA record, which
 * only the run's owner can read. Nothing is shown for a run with no checks, or when they cannot be read: a wrong line is worse than
 * none. `brief` is the product's view, without counts. */
export function QALine({ apiBase, jobId, brief }: { apiBase: string; jobId: string; brief: boolean }) {
  const [record, setRecord] = useState<QARecord | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setRecord(null);
    getQARecord(apiBase, jobId, controller.signal).then(setRecord, () => setRecord(null));
    return () => controller.abort();
  }, [apiBase, jobId]);
  const line = qaLine(record, brief);
  if (!line) return null;
  return (
    <details className="studio-qa" data-testid="qa-line" data-verdict={record?.verdict}>
      <summary className={line.tone === "ok" ? "studio-ok" : line.tone === "warn" ? "studio-warn" : "studio-problem"}>{line.line}</summary>
      <ul>
        {qaItems(record, brief).map((item, i) => (
          <li key={i} data-verdict={item.verdict}><b>{item.label}</b>: {item.message}</li>
        ))}
      </ul>
    </details>
  );
}
