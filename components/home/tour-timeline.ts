/** The tour's clock (the scroll-driven tour of the home page's calculator). Time is scroll: `t` is how far the page has
 * scrolled into the tour, in viewport heights. Nothing here knows a laminate quantity; it only says what is on screen when. */

export const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
/** 0 before `from`, 1 after `to`, linear between. */
export const span = (t: number, from: number, to: number) => clamp01((t - from) / (to - from));
export const smooth = (x: number) => x * x * (3 - 2 * x);

/** Values at given times, eased between neighbours and held outside them. */
export function keyed(keys: [number, number][], t: number): number {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [time, value] = keys[i];
    if (t <= time) {
      const [before, start] = keys[i - 1];
      return start + (value - start) * smooth(span(t, before, time));
    }
  }
  return keys[keys.length - 1][1];
}

/** The bridge from the hero's clip into the 3D view takes the first screen of scroll. */
export const BRIDGE = 1;
export const STEP_IDS = ["material", "layup", "engine", "loads", "handover"] as const;
export type StepId = (typeof STEP_IDS)[number];
/** How many screens of scroll each step takes. */
const LENGTHS: Record<StepId, number> = { material: 0.8, layup: 1.1, engine: 0.8, loads: 0.9, handover: 0.45 };

export type StepRange = { id: StepId; start: number; end: number; at: (u: number) => number };
export const STEPS: StepRange[] = (() => {
  let start = BRIDGE;
  return STEP_IDS.map((id) => {
    const from = start;
    const end = from + LENGTHS[id];
    start = end;
    return { id, start: from, end, at: (u: number) => from + (end - from) * u };
  });
})();
/** The whole pinned sequence, in screens: after it the stage lets go and the page scrolls on as usual. */
export const TOTAL = STEPS[STEPS.length - 1].end;
const [MATERIAL, LAYUP, ENGINE, LOADS, HANDOVER] = STEPS;
/** The first step's words come in as the bridge ends. */
const FIRST_STEP_FROM = BRIDGE - 0.1;

/** When each ply starts to come down as the layup is typed, on a clock of one unit per character. A listed ply starts when the
 * slash or the bracket that ends its angle is typed; a mirrored one follows the `s`. */
export type LayupScript = { text: string; starts: number[]; end: number };
const PLY_FALL = 1.3; // clock units a ply takes to come down
const AFTER_TYPING = 1.4; // clock units between the plies that follow the typing

export function layupScript(text: string, plyCount: number, symmetric: boolean): LayupScript {
  const listed: number[] = [];
  for (let i = 0; i < text.length; i++) if (text[i] === "/" || text[i] === "]") listed.push(i + 1);
  const after = (count: number) => Array.from({ length: count }, (_, j) => text.length + 0.4 + j * AFTER_TYPING);
  // A notation this plain reading does not follow (a repeat, a ± sign): every ply comes down after the typing, evenly.
  const follows = listed.length === (symmetric ? plyCount / 2 : plyCount);
  const starts = follows ? [...listed, ...(symmetric ? after(plyCount - listed.length) : [])] : after(plyCount);
  return { text, starts, end: Math.max(text.length, ...starts.map((start) => start + PLY_FALL)) };
}

function laidAt(script: LayupScript, clock: number): number {
  return script.starts.reduce((sum, start) => sum + clamp01((clock - start) / PLY_FALL), 0);
}

/** What the tour shows at one moment. Every field is quantised, so the page renders again only when something visible changed. */
export type TourView = {
  /** The step whose words and panel are up: an index into STEP_IDS, or -1 while the bridge plays. */
  step: number;
  /** The material is picked in the library list. */
  picked: boolean;
  /** How much of the material's constants is typed into their tiles, 0 to 1. */
  constants: number;
  /** Characters of the layup typed so far. */
  layupChars: number;
  /** Plies laid, bottom first; fractional while one comes down. */
  laid: number;
  /** The ply thickness is shown. */
  thickness: boolean;
  /** The engine step: 0 nothing yet, 1 the request is shown as sent, 2 the description, 3 the matrices too. */
  engine: 0 | 1 | 2 | 3;
  /** Characters of the load typed so far. */
  loadChars: number;
  /** The load is typed in full: the loaded case may be asked for and its answer shown. */
  loaded: boolean;
  /** The first ply to fail may be marked in the view. */
  mark: boolean;
  /** How far apart the plies stand, 0 to 1. */
  explode: number;
  /** The camera's turn in degrees. */
  azimuth: number;
};

/** The camera's turn when the hero's clip lands on the top ply, and how far it turns on from there to the end of the tour. At
 * -24° the ply's long edges lie nearly level on screen, so the clip lies back onto it with hardly a twist; the turn then ends at
 * 0°, the view's resting position, which is where the calculator below shows the same stack. */
export const AZIMUTH_START = -24;
const AZIMUTH_SWEEP = 24;
export const azimuthAt = (t: number) => AZIMUTH_START + AZIMUTH_SWEEP * span(t, BRIDGE, TOTAL);
/** The plies separate in the last fifth of the bridge, once the clip has become the top ply. */
export const BRIDGE_EXPLODE_FROM = 0.8;

const round = (value: number, steps: number) => Math.round(value * steps) / steps;

export function viewAt(t: number, script: LayupScript, plyCount: number, loadText: string): TourView {
  const step = t < FIRST_STEP_FROM ? -1 : Math.max(0, STEPS.findIndex((range) => t < range.end));
  const index = t >= TOTAL ? STEPS.length - 1 : step;
  const material = span(t, MATERIAL.start, MATERIAL.end);
  const layup = span(t, LAYUP.start, LAYUP.end);
  const engine = span(t, ENGINE.start, ENGINE.end);
  const loads = span(t, LOADS.start, LOADS.end);
  const clock = span(layup, 0.1, 0.8) * script.end;
  const cleared = LAYUP.at(0.06);
  const laid = t < cleared ? plyCount * (1 - span(t, MATERIAL.at(0.8), cleared)) : laidAt(script, clock);
  const explode = keyed([
    [BRIDGE_EXPLODE_FROM, 0], [BRIDGE, 1], // the plies separate as the bridge ends
    [MATERIAL.at(0.35), 0.62], // and settle, still apart
    [LAYUP.at(0.8), 0.62], [LAYUP.at(0.97), 0.12], // the laid plies close up
    [ENGINE.at(0.02), 0.12], [ENGINE.at(0.16), 0], // one laminate for the engine
    [LOADS.at(0.4), 0], [LOADS.at(0.62), 0.6], // opened again, to show the ply that fails first
    [HANDOVER.at(0.05), 0.6], [HANDOVER.at(0.7), 0], // and closed for the hand-over
  ], t);
  return {
    step: index,
    picked: material >= 0.1,
    constants: round(span(material, 0.18, 0.62), 40),
    layupChars: Math.min(script.text.length, Math.floor(clock + 1e-6)),
    laid: round(laid, 50),
    thickness: layup >= 0.05,
    engine: engine >= 0.52 ? 3 : engine >= 0.36 ? 2 : engine >= 0.1 ? 1 : 0,
    loadChars: Math.min(loadText.length, Math.floor(span(loads, 0.12, 0.36) * loadText.length + 1e-6)),
    loaded: loads >= 0.4,
    mark: loads >= 0.5 && t < HANDOVER.at(0.35),
    explode: round(explode, 100),
    azimuth: round(azimuthAt(t), 5),
  };
}

/** Everything shown at once: what a visitor who asked for reduced motion, or a small screen, gets. */
export function finalView(script: LayupScript, plyCount: number, loadText: string): TourView {
  return {
    step: STEPS.length - 1, picked: true, constants: 1, layupChars: script.text.length, laid: plyCount, thickness: true,
    engine: 3, loadChars: loadText.length, loaded: true, mark: true, explode: 0, azimuth: 0,
  };
}

export function sameView(a: TourView, b: TourView): boolean {
  return (Object.keys(a) as (keyof TourView)[]).every((key) => a[key] === b[key]);
}
