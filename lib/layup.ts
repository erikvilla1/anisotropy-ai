import { parseLayup } from "./studio-chat";
import { PLY_KEYS } from "./studio-form";

/** The most plies a layup may list before the mirror, the coupon form's own limit; a symmetric stack draws twice that. */
export const MAX_PLIES = PLY_KEYS.length;

export type ExpandedLayup = { angles: number[]; symmetric: boolean };

/** Laminate notation to the list of ply angles, bottom face first (ADR-0004): `[45/-45/0/90]s` is 45, -45, 0, 90, 90, 0,
 * -45, 45. Notation only: the same reader the coupon chat uses (`lib/studio-chat.ts`), plus the mirror an `s` asks for.
 * No laminate quantity is computed here. */
export function expandLayup(text: string): { layup: ExpandedLayup; error?: undefined } | { layup?: undefined; error: string } {
  const trimmed = text.trim();
  if (!trimmed) return { error: "Type a layup, for example [45/-45/0/90]s." };
  const parsed = parseLayup(trimmed.startsWith("[") ? trimmed : `[${trimmed}]`);
  if (!parsed) {
    return {
      error: `Could not read the layup. Write angles separated by slashes, such as [0/90]s, [±45]2 or [0/45/-45/90], up to ${MAX_PLIES} listed plies.`,
    };
  }
  const angles = parsed.symmetric ? [...parsed.plies, ...[...parsed.plies].reverse()] : [...parsed.plies];
  return { layup: { angles, symmetric: parsed.symmetric } };
}

/** The notation for a list of angles, for the stack preview: no mirror detection, the plies as given. */
export function layupText(angles: number[]): string {
  return `[${angles.join("/")}]`;
}
