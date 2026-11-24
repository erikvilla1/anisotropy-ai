/** A run's quality checks and its verdict (ADR-0137), as the API's QA record serves them to the run's owner, and the one line the
 * run's panel shows of them. The verdict is the API's, which follows from the checks alone; the page computes nothing from them but
 * counts and words. */

export type QAVerdict = "blocked" | "needs engineer" | "ready" | "unchecked";
export type CheckVerdict = "pass" | "warn" | "block";

export type QACheck = {
  layer: "data" | "physics" | "fea" | "output" | "software";
  check: string;
  version: number;
  verdict: CheckVerdict;
  label: string;
  message: string;
  evidence: Record<string, unknown>;
  basis: string;
};

export type QARecord = { job_id: string; verdict: QAVerdict; counts: Record<CheckVerdict, number>; checks: QACheck[] };

const VERDICTS: readonly QAVerdict[] = ["blocked", "needs engineer", "ready", "unchecked"];
const CHECK_VERDICTS: readonly CheckVerdict[] = ["pass", "warn", "block"];

/** The API's answer as a QA record, or null when it is not one: the page then shows no line rather than a wrong one. */
export function readQARecord(payload: unknown): QARecord | null {
  if (typeof payload !== "object" || payload === null) return null;
  const p = payload as Record<string, unknown>;
  if (typeof p.job_id !== "string" || !VERDICTS.includes(p.verdict as QAVerdict) || !Array.isArray(p.checks)) return null;
  const checks = p.checks.filter((c): c is QACheck => typeof c === "object" && c !== null && CHECK_VERDICTS.includes((c as QACheck).verdict)
    && typeof (c as QACheck).label === "string" && typeof (c as QACheck).message === "string");
  if (checks.length !== p.checks.length) return null;
  const counts = { pass: 0, warn: 0, block: 0 };
  for (const c of checks) counts[c.verdict] += 1;
  return { job_id: p.job_id, verdict: p.verdict as QAVerdict, counts, checks };
}

export type QALine = { line: string; tone: "ok" | "warn" | "block" };

/** The run's quality checks in one line; null for a run with none. `brief`, the product's view: no counts, as for the second solver's
 * check (lib/studio-copy.ts, verificationOf), only what the customer should do with the result. */
export function qaLine(record: QARecord | null, brief = false): QALine | null {
  if (!record || record.verdict === "unchecked" || record.checks.length === 0) return null;
  const { pass, warn, block } = record.counts;
  const total = pass + warn + block;
  const checks = (n: number) => `${n} quality check${n === 1 ? "" : "s"}`;
  if (record.verdict === "blocked") {
    return { line: brief ? "A quality check stops this result: it should not be used as it stands"
      : `${checks(block)} ${block === 1 ? "blocks" : "block"} this result; ${pass} of ${total} passed`, tone: "block" };
  }
  if (record.verdict === "needs engineer") {
    return { line: brief ? "Quality checks passed with notes for an engineer to review"
      : `${pass} of ${checks(total)} passed; ${warn} ${warn === 1 ? "needs" : "need"} an engineer's review`, tone: "warn" };
  }
  return { line: brief ? "Every quality check passed" : `All ${checks(total)} passed`, tone: "ok" };
}

const VERDICT_WORDS: Record<CheckVerdict, string> = { pass: "passed", warn: "for an engineer to review", block: "stops this result" };

/** The checks to list under the line, the ones that need attention first, each in the customer's words. `brief`, the product's view:
 * each check's verdict in words instead of its message, which may hold counts a customer is not asked to judge. */
export function qaItems(record: QARecord | null, brief = false): { label: string; message: string; verdict: CheckVerdict }[] {
  if (!record) return [];
  const order: Record<CheckVerdict, number> = { block: 0, warn: 1, pass: 2 };
  return record.checks.map((c, i) => ({ c, i })).sort((a, b) => order[a.c.verdict] - order[b.c.verdict] || a.i - b.i)
    .map(({ c }) => ({ label: c.label, message: brief ? VERDICT_WORDS[c.verdict] : c.message, verdict: c.verdict }));
}
