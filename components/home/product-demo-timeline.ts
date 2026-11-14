/** The product demo's clock (ADR-0095, ADR-0098): what the home page's demonstration shows when. Four beats, played one whole
 * beat per scroll gesture by components/home/tour-driver.ts: a wing as one part, the wing apart into its parts, the analysis
 * on every part, and the wing whole again. `t` is the demo's own time; it stands still at a stop and runs at one speed while a
 * beat plays. Nothing here knows a number of the record; it only says what is on screen when. */

export const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
/** 0 before `from`, 1 after `to`, linear between. */
export const span = (t: number, from: number, to: number) => clamp01((t - from) / (to - from));
/** Ease in and out. */
export const smooth = (x: number) => x * x * (3 - 2 * x);

export const BEAT_IDS = ["describe", "model", "analysis", "report"] as const;
export type BeatId = (typeof BEAT_IDS)[number];
/** The clock's one speed while a beat plays, in units a second: one unit is four seconds. */
export const DEMO_CLOCK_PER_SECOND = 0.25;
/** How long each beat is on the clock: 3.2, 3.6, 4.8 and 3.2 s. */
const LENGTHS: Record<BeatId, number> = { describe: 0.8, model: 0.9, analysis: 1.2, report: 0.8 };
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
 * radians: `pitch` leans the wing's upper face back from the viewer, `yaw` turns it about the upright axis; `explode` is how
 * far its parts stand apart, 0 to 1; `size` is the wing's span as a share of the box's width. */
export type Pose = { x: number; y: number; pitch: number; yaw: number; explode: number; size: number };
const START: Pose = { x: 0.5, y: 0.32, pitch: 0.62, yaw: -0.7, explode: 0, size: 0.56 };
/** The pose at the end of each beat, Scale's way: whole in the middle, seen from above and from its tip so the aerofoil shows;
 * then apart at one side; then at the other, turned to show the parts' other ends; then whole in the middle again. */
export const POSES: Record<BeatId, Pose> = {
  describe: { x: 0.5, y: 0.31, pitch: 0.72, yaw: -0.88, explode: 0, size: 0.66 },
  model: { x: 0.68, y: 0.5, pitch: 0.82, yaw: -1.0, explode: 1, size: 0.54 },
  analysis: { x: 0.32, y: 0.5, pitch: 0.82, yaw: 0.98, explode: 1, size: 0.54 },
  report: { x: 0.5, y: 0.31, pitch: 0.7, yaw: -0.8, explode: 0, size: 0.66 },
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
  /** The wing is there at all, 0 to 1: it fades in as the first beat starts. */
  presence: number;
  /** How much of the mesh is drawn, 0 to 1. */
  mesh: number;
  /** How far the parts have taken the analysis's colours, 0 to 1. */
  field: number;
};

// Within the first beat: the wing comes in, and what it is fills in beside it.
const FACTS_FROM = DESCRIBE.at(0.35);
const FACTS_TO = DESCRIBE.at(0.85);
// Within the second: the parts are named as they stand apart, and the mesh is drawn on them.
const PARTS_FROM = MODEL.at(0.35);
const PARTS_TO = MODEL.at(0.88);
const MESH_FROM = MODEL.at(0.4);
const MESH_TO = MODEL.at(0.95);
// Within the third: the run's stages, then the colours and what they say.
const STAGES_FROM = ANALYSIS.at(0.25);
const STAGES_TO = ANALYSIS.at(0.65);
const FIELD_FROM = ANALYSIS.at(0.65);
const FIELD_TO = ANALYSIS.at(0.88);
const RESULT_AT = ANALYSIS.at(0.82);
// Within the fourth: the wing closes, coloured, and the files are listed.
const FILES_FROM = REPORT.at(0.55);
const FILES_TO = REPORT.at(0.92);

export function sceneAt(t: number): DemoScene {
  return {
    presence: smooth(span(t, 0, DESCRIBE.at(0.25))),
    mesh: smooth(span(t, MESH_FROM, MESH_TO)),
    field: smooth(span(t, FIELD_FROM, FIELD_TO)),
  };
}

/** How many of each list the page shows: the wing's facts, its parts, the run's stages and the files. */
export type DemoCounts = { facts: number; parts: number; stages: number; files: number };

/** What the page shows at one moment. Every field is quantised, so the page renders again only when something visible changed. */
export type DemoView = {
  /** The beat whose words are up: an index into BEAT_IDS. */
  beat: number;
  /** How far the words of that beat are in, 0 to 1 in twentieths. */
  words: number;
  /** Facts about the wing filled in, 0 to `facts`. */
  facts: number;
  /** Parts named, 0 to `parts`. */
  parts: number;
  /** Stages of the run done, 0 to `stages`; the one after them is the one going. */
  stage: number;
  /** The field's legend is up. */
  legend: boolean;
  /** What the analysis found is up. */
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

export function viewAt(t: number, counts: DemoCounts): DemoView {
  // The beat whose words are up: the one before stays until its words have gone.
  let beat = 0;
  for (let i = 1; i < BEATS.length; i++) if (t > BEATS[i].start + WORDS_OUT) beat = i;
  return {
    beat,
    words: Math.round(wordsOf(beat, t) * 20) / 20,
    facts: Math.floor(span(t, FACTS_FROM, FACTS_TO) * counts.facts + 1e-9),
    parts: Math.floor(span(t, PARTS_FROM, PARTS_TO) * counts.parts + 1e-9),
    stage: Math.floor(span(t, STAGES_FROM, STAGES_TO) * counts.stages + 1e-9),
    legend: t >= FIELD_FROM + 0.02,
    result: t >= RESULT_AT,
    files: Math.floor(span(t, FILES_FROM, FILES_TO) * counts.files + 1e-9),
  };
}

export const sameView = (a: DemoView, b: DemoView) =>
  a.beat === b.beat && a.words === b.words && a.facts === b.facts && a.parts === b.parts && a.stage === b.stage &&
  a.legend === b.legend && a.result === b.result && a.files === b.files;

/** Everything shown, each beat finished: what the ordinary section shows when nothing plays. */
export const finalView = (counts: DemoCounts): DemoView => viewAt(DEMO_TOTAL, counts);
