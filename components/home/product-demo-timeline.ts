/** The product demo's clock (ADR-0095): what the home page's demonstration of the coupon workspace shows when. Four beats, played
 * one whole beat per scroll gesture by components/home/tour-driver.ts. `t` is the demo's own time; it stands still at a stop and
 * runs at one speed while a beat plays. Nothing here knows a number of the recorded run; it only says what is on screen when. */

export const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
/** 0 before `from`, 1 after `to`, linear between. */
export const span = (t: number, from: number, to: number) => clamp01((t - from) / (to - from));
/** Ease in and out. */
export const smooth = (x: number) => x * x * (3 - 2 * x);

export const BEAT_IDS = ["describe", "model", "analysis", "report"] as const;
export type BeatId = (typeof BEAT_IDS)[number];
/** The clock's one speed while a beat plays, in units a second: one unit is four seconds. */
export const DEMO_CLOCK_PER_SECOND = 0.25;
/** How long each beat is on the clock: 4.4, 3.2, 5.6 and 2.8 s. */
const LENGTHS: Record<BeatId, number> = { describe: 1.1, model: 0.8, analysis: 1.4, report: 0.7 };
/** The model's move at the start of a beat: 1.44 s, eased in and out, as Scale's centre model moves. */
export const MOVE = 0.36;
/** The words of the beat before go in this long, as the move starts. */
const WORDS_OUT = 0.09;

export type Beat = { id: BeatId; start: number; end: number; at: (u: number) => number };
export const BEATS: Beat[] = (() => {
  let start = 0;
  return BEAT_IDS.map((id) => {
    const from = start;
    const end = from + LENGTHS[id];
    start = end;
    return { id, start: from, end, at: (u: number) => from + (end - from) * u };
  });
})();
export const DEMO_TOTAL = BEATS[BEATS.length - 1].end;
/** Where the clock stands still: at 0 while the box is empty, then at the end of each beat. */
export const DEMO_STOPS: number[] = [0, ...BEATS.map((beat) => beat.end)];
const [DESCRIBE, MODEL, ANALYSIS, REPORT] = BEATS;

/** Where the model is and how it is turned. `x` and `y` are shares of the box, from its left and its top; the angles are
 * radians: `pitch` leans the laminate's face back from the viewer, `yaw` turns it about the upright axis; `explode` is how far
 * the plies stand apart, 0 to 1; `size` is the coupon's length as a share of the box's width. */
export type Pose = { x: number; y: number; pitch: number; yaw: number; explode: number; size: number };
const START: Pose = { x: 0.5, y: 0.3, pitch: 0.42, yaw: 0, explode: 0.3, size: 0.4 };
/** The pose at the end of each beat, Scale's way: in the middle and nearly face-on, then three-quarter at one side, then at the
 * other with the plies apart, then back in the middle. */
export const POSES: Record<BeatId, Pose> = {
  describe: { x: 0.5, y: 0.25, pitch: 0.66, yaw: 0.1, explode: 0.5, size: 0.44 },
  model: { x: 0.7, y: 0.48, pitch: 0.92, yaw: -0.7, explode: 0, size: 0.46 },
  analysis: { x: 0.3, y: 0.5, pitch: 0.98, yaw: 0.6, explode: 1, size: 0.38 },
  report: { x: 0.5, y: 0.25, pitch: 0.72, yaw: -0.16, explode: 0.5, size: 0.4 },
};
const mix = (a: number, b: number, u: number) => a + (b - a) * u;
const between = (a: Pose, b: Pose, u: number): Pose => ({
  x: mix(a.x, b.x, u), y: mix(a.y, b.y, u), pitch: mix(a.pitch, b.pitch, u), yaw: mix(a.yaw, b.yaw, u), explode: mix(a.explode, b.explode, u), size: mix(a.size, b.size, u),
});

/** The model's pose at one moment: each beat begins with one eased move from the pose before to its own. */
export function poseAt(t: number): Pose {
  let pose = START;
  for (const beat of BEATS) {
    if (t <= beat.start) break;
    const moved = smooth(span(t, beat.start, beat.start + MOVE));
    pose = moved >= 1 ? POSES[beat.id] : between(pose, POSES[beat.id], moved); // the move ends on the pose itself, not on a sum beside it
  }
  return pose;
}

/** What the 3D view draws at one moment, beside the pose. */
export type DemoScene = {
  /** The model is there at all, 0 to 1: it fades in as the first beat starts. */
  presence: number;
  /** Plies laid, bottom first; fractional while one comes down. */
  laid: number;
  /** How much of the mesh is drawn, 0 to 1. */
  mesh: number;
  /** How far the plies have taken the stress field's colours, 0 to 1. */
  field: number;
};

/** When each ply starts to come down as the layup is typed, on a clock of one unit per character: a listed ply when the slash
 * or the bracket that ends its angle is typed, a mirrored one after the `s`. */
export type LayupScript = { text: string; starts: number[]; end: number };
const PLY_FALL = 1.6;
export function layupScript(text: string, plyCount: number): LayupScript {
  const listed: number[] = [];
  for (let i = 0; i < text.length; i++) if (text[i] === "/" || text[i] === "]") listed.push(i + 1);
  const rest = Math.max(0, plyCount - listed.length);
  const starts = [...listed.slice(0, plyCount), ...Array.from({ length: rest }, (_, j) => text.length + 0.4 + j * 1.5)];
  return { text, starts, end: Math.max(text.length, ...starts.map((start) => start + PLY_FALL)) };
}
const laidAt = (script: LayupScript, clock: number) => script.starts.reduce((sum, start) => sum + clamp01((clock - start) / PLY_FALL), 0);

// Within the first beat: the model and the words come in, the material and the standard are picked, the layup is typed.
const PICK_AT = DESCRIBE.at(0.3);
const STANDARD_AT = DESCRIBE.at(0.4);
const TYPE_FROM = DESCRIBE.at(0.48);
const TYPE_TO = DESCRIBE.at(0.96);
// Within the second: the summary's cells fill and the mesh is drawn.
const CELLS_FROM = MODEL.at(0.5);
const CELLS_TO = MODEL.at(0.9);
const MESH_FROM = MODEL.at(0.4);
const MESH_TO = MODEL.at(0.95);
// Within the third: the run's stages, then the field and what it says.
const STAGES_FROM = ANALYSIS.at(0.3);
const STAGES_TO = ANALYSIS.at(0.7);
const FIELD_FROM = ANALYSIS.at(0.7);
const FIELD_TO = ANALYSIS.at(0.9);
const RESULT_AT = ANALYSIS.at(0.84);
// Within the fourth: the files, one after another.
const FILES_FROM = REPORT.at(0.55);
const FILES_TO = REPORT.at(0.92);

export function sceneAt(t: number, script: LayupScript): DemoScene {
  return {
    presence: smooth(span(t, 0, DESCRIBE.at(0.22))),
    laid: laidAt(script, span(t, TYPE_FROM, TYPE_TO) * script.end),
    mesh: smooth(span(t, MESH_FROM, MESH_TO)),
    field: smooth(span(t, FIELD_FROM, FIELD_TO)),
  };
}

/** What the page shows at one moment. Every field is quantised, so the page renders again only when something visible changed. */
export type DemoView = {
  /** The beat whose words are up: an index into BEAT_IDS. */
  beat: number;
  /** How far the words of that beat are in, 0 to 1 in twentieths. */
  words: number;
  /** A material is picked in the assistant's chips. */
  picked: boolean;
  /** The standard is picked. */
  standard: boolean;
  /** Characters of the layup typed so far. */
  layupChars: number;
  /** Cells of the setup's summary filled, 0 to `cells`. */
  cells: number;
  /** Stages of the run done, 0 to `stages`; the one after them is the one going. */
  stage: number;
  /** The field's legend is up. */
  legend: boolean;
  /** What the run found is up. */
  result: boolean;
  /** Files listed, 0 to `files`. */
  files: number;
};

/** How far a beat's words are in: they come in after the model has begun to move and go as the next beat's move starts. */
function wordsOf(index: number, t: number): number {
  const beat = BEATS[index];
  const from = beat.start + (index === 0 ? 0.08 : MOVE * 0.55);
  const coming = smooth(span(t, from, from + 0.2));
  const going = index === BEATS.length - 1 ? 1 : 1 - smooth(span(t, beat.end, beat.end + WORDS_OUT));
  return Math.min(coming, going);
}

export function viewAt(t: number, script: LayupScript, counts: { cells: number; stages: number; files: number }): DemoView {
  // The beat whose words are up: the one before stays until its words have gone.
  let beat = 0;
  for (let i = 1; i < BEATS.length; i++) if (t > BEATS[i].start + WORDS_OUT) beat = i;
  return {
    beat,
    words: Math.round(wordsOf(beat, t) * 20) / 20,
    picked: t >= PICK_AT,
    standard: t >= STANDARD_AT,
    layupChars: Math.min(script.text.length, Math.floor(span(t, TYPE_FROM, TYPE_TO) * script.end + 1e-9)),
    cells: Math.floor(span(t, CELLS_FROM, CELLS_TO) * counts.cells + 1e-9),
    stage: Math.floor(span(t, STAGES_FROM, STAGES_TO) * counts.stages + 1e-9),
    legend: t >= FIELD_FROM + 0.02,
    result: t >= RESULT_AT,
    files: Math.floor(span(t, FILES_FROM, FILES_TO) * counts.files + 1e-9),
  };
}

export const sameView = (a: DemoView, b: DemoView) =>
  a.beat === b.beat && a.words === b.words && a.picked === b.picked && a.standard === b.standard && a.layupChars === b.layupChars &&
  a.cells === b.cells && a.stage === b.stage && a.legend === b.legend && a.result === b.result && a.files === b.files;

/** Everything shown, each beat finished: what the ordinary section shows when nothing plays. */
export const finalView = (script: LayupScript, counts: { cells: number; stages: number; files: number }): DemoView => viewAt(DEMO_TOTAL, script, counts);
