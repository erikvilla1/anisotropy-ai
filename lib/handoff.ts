/** A message carried from one page to another (ADR-0124): the home page's box, the start screen's box and a section's chat leave it in
 * this tab's session storage, and the assistant of the page opened reads it once. `setUp` is the message that set a blank FEA project
 * up for a kind of work, shown at the head of that kind's chat so the talk reads on; `prompt` is the message the chat then reads. */

export const HANDOFF_KEY = "composite-scope-handoff";

export type Handoff = { prompt: string; setUp: string };

type SessionLike = { getItem(key: string): string | null; setItem(key: string, value: string): void; removeItem(key: string): void };

const LIMIT = 2000; // characters, as the chat's own box

export function putHandoff(storage: SessionLike | null | undefined, handoff: Partial<Handoff>): boolean {
  const payload = { prompt: (handoff.prompt ?? "").trim().slice(0, LIMIT), setUp: (handoff.setUp ?? "").trim().slice(0, LIMIT) };
  if (!payload.prompt && !payload.setUp) return true;
  try { storage?.setItem(HANDOFF_KEY, JSON.stringify(payload)); return Boolean(storage); } catch { return false; }
}

/** The message left for this page, once: read and removed. Empty where nothing was left or storage is blocked. */
export function takeHandoff(storage: SessionLike | null | undefined): Handoff {
  const none = { prompt: "", setUp: "" };
  try {
    const stored = storage?.getItem(HANDOFF_KEY);
    if (!stored) return none;
    storage?.removeItem(HANDOFF_KEY);
    const payload = JSON.parse(stored) as { prompt?: unknown; setUp?: unknown };
    return { prompt: typeof payload.prompt === "string" ? payload.prompt.trim().slice(0, LIMIT) : "",
      setUp: typeof payload.setUp === "string" ? payload.setUp.trim().slice(0, LIMIT) : "" };
  } catch {
    return none;
  }
}
