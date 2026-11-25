/** What a run of the site check may spend, and what the month has spent (ADR-0138). The founder's cap, 2026-11-24: one dollar a run, a
 * full run every four days; twenty dollars a month stays as the ceiling. A question the site reads with a model is asked only while its
 * likely cost, with the judge's share kept back, fits what is left. */

/** The spend of one run, as the ledger keeps it. */
export type Entry = { at: string; mode: string; site: number; judge: number; models?: number };

export const RUN_CAP = 1;
export const MONTH_CAP = 20;
/** What one question the site reads with a model is reckoned to cost before any has been measured, on the high side: the site's model
 * (`claude-opus-5-5`) reads a question in about 3,000 tokens and writes a few hundred, near $0.02, and a question of the setup that
 * reads nothing is sent twice. */
export const FIRST_GUESS = 0.04;
/** What the judge is reckoned to cost for each answer it has not graded before (`claude-haiku-5-5`, about 4,000 tokens in). */
export const JUDGE_EACH = 0.001;

/** What an answer's `X-Anisotropy-Model-Cost` header says its calls cost: "<dollars>; calls=<n>; unpriced=<n>" (api/main.py). An unpriced
 * call, or a call with no header (a site from before the header), is counted at the first guess. */
export function headerCost(header: string | undefined | null, calls: number): { dollars: number; calls: number } {
  if (!header) return { dollars: calls * FIRST_GUESS, calls };
  const m = /^\s*([\d.]+)\s*;\s*calls=(\d+)\s*;\s*unpriced=(\d+)/.exec(header);
  if (!m) return { dollars: Math.max(1, calls) * FIRST_GUESS, calls: Math.max(1, calls) };
  return { dollars: Number(m[1]) + Number(m[3]) * FIRST_GUESS, calls: Number(m[2]) };
}

/** The dollars the month of `now` has spent, from the ledger. */
export function monthSpent(ledger: readonly Entry[], now: Date): number {
  const month = now.toISOString().slice(0, 7);
  return ledger.filter((e) => e.at.slice(0, 7) === month).reduce((sum, e) => sum + e.site + e.judge, 0);
}

/** A run's spending: what the site's model has cost so far, measured from each answer, against the run's cap. */
export class Budget {
  site = 0;
  questions = 0;

  /** `cap`: the most this run may spend, the month's ceiling taken into account; `judging`: the answers the judge may have to grade. */
  constructor(readonly cap: number, private readonly judging: number) {}

  /** What the next question the site reads with a model is likely to cost: the mean so far, or the first guess. */
  get next(): number {
    return this.questions ? Math.max(this.site / this.questions, 0.005) : FIRST_GUESS;
  }

  /** Whether one more question the site reads with a model fits, with the judge's share kept back. */
  fits(): boolean {
    return this.site + this.next + this.judging * JUDGE_EACH <= this.cap;
  }

  /** A question's measured cost. */
  add(dollars: number): void {
    this.site += dollars;
    this.questions += 1;
  }

  /** What is left for the judge. */
  get left(): number {
    return Math.max(0, this.cap - this.site);
  }
}

/** The cap of a run: the cap asked for, no more than what the month has left. */
export function runCap(asked: number, ledger: readonly Entry[], now: Date, month = MONTH_CAP): number {
  return Math.max(0, Math.min(asked, month - monthSpent(ledger, now)));
}

/** How many questions the site reads with a model fit a run's cap: at the mean the ledger measured over the last runs that asked any, or
 * the first guess, with a tenth of the cap kept back for the judge. */
export function modelSlots(cap: number, ledger: readonly Entry[]): number {
  const measured = ledger.filter((e) => (e.models ?? 0) > 0).slice(-5);
  const count = measured.reduce((n, e) => n + (e.models ?? 0), 0);
  const each = count ? Math.max(measured.reduce((d, e) => d + e.site, 0) / count, 0.005) : FIRST_GUESS;
  return Math.max(0, Math.floor((cap * 0.9) / each));
}
