import { missingIn, STEP_ORDER } from "./studio-chat";
import type { StudioForm, StudioValues } from "./studio-form";

/** When the page asks our kernel for a live solve (ADR-0086): after the last edit has settled for LIVE_DEBOUNCE_MS, once the setup has
 * every row the conversation asks for, when the rows differ from the last ones sent, and never while a full run is going. The page computes
 * nothing; this decides only when to ask. */
export const LIVE_DEBOUNCE_MS = 800;

/** The rows as sent, as one string: two edits that leave the same rows send nothing new. */
export const liveKey = (values: StudioValues): string => JSON.stringify(values);

export type LiveCondition = {
  /** every row the setup needs is filled (the conversation's last step is the review) */
  complete: boolean;
  /** a full run is going: its answer is on its way and a preview would only compete with it */
  running: boolean;
  /** the fibre tow test has no model to solve (ADR-0074) */
  tow: boolean;
  key: string;
  /** the rows last sent, or null */
  sent: string | null;
  /** the page has the API's address */
  api: boolean;
};

export function shouldSolveLive(c: LiveCondition): boolean {
  return c.api && c.complete && !c.running && !c.tow && c.key !== c.sent;
}

/** Every row the setup needs, by the conversation's own steps (`missingIn`), but the engineer's name, which the rail fills from Run by as it
 * does when it solves; without one, the check says so. */
export function setupComplete(form: StudioForm): boolean {
  return STEP_ORDER.filter((step) => step !== "name" && step !== "review").every((step) => missingIn(step, form).length === 0);
}
