import timing from "@/components/home/hero-lens.json";

/** The hero lens's loop (ADR-0071): when each model fills the lens, as scripts/hero-lens.ts wrote it with the recording. */
export const LENS_TIMING: { duration: number; segments: { id: string; start: number; end: number }[] } = timing;

/** What each model in the loop is, in the caption's two lines. No result values: a number on the site needs a run record behind it. */
export const LENS_CAPTIONS: Record<string, [string, string]> = {
  tension: ["UNNOTCHED TENSION", "IM7/8552 [45/0/-45/90]s · DISPLACEMENT"],
  bending: ["THREE-POINT BENDING", "IM7/8552 [45/0/-45/90]s · DISPLACEMENT"],
  plate: ["PLATE UNDER PRESSURE", "SIX SUPPORTS · DISPLACEMENT"],
};

/** The model on screen at a time in the loop: the segment holding it, or the first model, which the loop's end fades back to. */
export function lensModelAt(seconds: number): string {
  return LENS_TIMING.segments.find((s) => seconds >= s.start && seconds < s.end)?.id ?? LENS_TIMING.segments[0].id;
}
