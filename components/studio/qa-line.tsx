"use client";

import { useEffect, useState } from "react";
import { QA_UNRECORDED, qaItems, qaLine, type QARecord } from "@/lib/qa";
import { getQARecord } from "@/lib/studio-api";

const RETRY_MS = 3000; // a run's record is written just after its row says done: one more read, a moment later, before saying it is missing

/** A done run's quality checks in one line, with the checks folded under it (ADR-0137): read from the run's QA record, which only the
 * run's owner can read, once more a moment later when the first read finds none. A run that wrote checks but whose record has none
 * says so, rather than showing nothing; a run that wrote none shows nothing. `brief` is the product's view, without counts. */
export function QALine({ apiBase, jobId, brief, expected }: { apiBase: string; jobId: string; brief: boolean; /** the run wrote its checks */ expected: boolean }) {
  const [record, setRecord] = useState<QARecord | null>(null);
  const [settled, setSettled] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setRecord(null);
    setSettled(false);
    const read = (again: boolean) => {
      getQARecord(apiBase, jobId, controller.signal).then((found) => {
        if (controller.signal.aborted) return;
        if (again && (!found || found.verdict === "unchecked")) {
          timer = setTimeout(() => read(false), RETRY_MS);
          return;
        }
        setRecord(found);
        setSettled(true);
      }, () => {
        if (controller.signal.aborted) return;
        setRecord(null);
        setSettled(true);
      });
    };
    read(true);
    return () => {
      controller.abort();
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [apiBase, jobId]);
  const line = qaLine(record, brief);
  if (!line) {
    return settled && expected ? <p className="studio-muted" data-testid="qa-line" data-verdict="unrecorded">{QA_UNRECORDED}</p> : null;
  }
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
