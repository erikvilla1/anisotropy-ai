/** The product demo's words (ADR-0095, ADR-0098), in one place so the unit test can read every one against the product view's
 * banned terms (lib/studio-copy.ts, ADR-0091). The names of the run's stages and the files are the workspace's own and are
 * imported where they are shown; the numbers are the record's (lib/demo-wing.ts). */
import { BEND_DRAWN, metres, ribCount, type DemoWing } from "@/lib/demo-wing";
import type { BeatId } from "./product-demo-timeline";

export const DEMO_HEAD = { label: "THE WORKSPACE / ONE PART, START TO FINISH", title: "A wing, analysed part by part." };

export const BEAT_COPY: Record<BeatId, { label: string; title: string; text: string }> = {
  describe: {
    label: "PART",
    title: "Start from the part.",
    text: "A composite wing: two skins over two spars and a row of ribs, each a laminate with its own plies.",
  },
  model: {
    label: "BREAKDOWN",
    title: "It comes apart into its parts.",
    text: "Every part gets its layup and its mesh. There is nothing to draw by hand.",
  },
  analysis: {
    label: "ANALYSIS",
    title: "Every part is analysed.",
    text: "The stress in every ply is set against its strength, part by part.",
  },
  report: {
    label: "REPORT",
    title: "Back together, with the report.",
    // The About page's sentence, word for word.
    text: "Less time on repetitive setup and documentation, more time optimizing the structure.",
  },
};

export const FILES_HEAD = "A full run writes";
/** Once the demo has played: the wing can be turned by hand. */
export const TURN_HINT = "Drag the wing to turn it";
/** Under the result: the bend is drawn larger than it is. */
export const BEND_NOTE = `The bend is drawn ${BEND_DRAWN} times its size.`;
export const OPEN_WORKSPACE = "Open the workspace";

/** What the wing is, as the workspace's strip names its cells. */
export function wingFacts(wing: DemoWing, material: string): [string, string][] {
  return [
    ["PART", "Wing, one side"],
    ["SPAN", metres(wing.wing.span)],
    ["CHORD", `${metres(wing.wing.root_chord)} at the root, ${metres(wing.wing.tip_chord)} at the tip`],
    ["MATERIAL", material],
    ["STRUCTURE", `2 skins, ${wing.wing.spars.length} spars, ${ribCount(wing)} ribs`], // the wing's ribs and the winglet's
    // The span and the chords above are the wing's own, to the rib where the winglet begins; the winglet is stated apart.
    ["WINGLET", `${metres(wing.wing.winglet.rise)} tall, canted ${Math.round(wing.wing.winglet.cant)}°`],
  ];
}

/** The parts and their layups, in the record's order. */
export const wingParts = (wing: DemoWing): [string, string][] => wing.parts.map((part) => [part.name.toUpperCase(), part.layup]);

/** A share as a whole percentage: 0.412 is "41 %". */
const percent = (share: number): string => `${Math.round(share * 100)} %`;

/** What the analysis found, in two short lines; null until the analysis is recorded. */
export function resultLines(wing: DemoWing): { first: string; when: string } | null {
  const { solve, load, field } = wing;
  if (!solve || !load || !field) return null;
  const part = wing.parts.find((candidate) => candidate.id === solve.governing.part);
  const name = (part?.name ?? solve.governing.part).toLowerCase();
  const where = solve.governing.at < 0.1 * wing.wing.span ? "at the root" : `${metres(solve.governing.at)} from the root`;
  const used = field.unit ? `${solve.governing.value} ${field.unit}` : `${percent(solve.governing.value)} of its strength used`;
  const how = solve.governing.mode && solve.governing.ply ? `, in ${solve.governing.mode} in ply ${solve.governing.ply}` : "";
  return {
    first: `Most loaded: the ${name} ${where}, ${used}${how}.`,
    // The load lies on the wing's own ribs, none on the winglet; the largest rise is at the winglet's tip, which stands
    // furthest out.
    when: `Held at the root with ${load.total} ${load.unit} pushed up at the wing's ribs; the winglet's tip rises ${Math.round(solve.tip_deflection)} ${wing.units.length}.`,
  };
}

/** Every fixed sentence the demo shows, for the banned-term check. */
export function everyLine(wing: DemoWing, material: string): string[] {
  const result = resultLines(wing);
  return [
    DEMO_HEAD.label, DEMO_HEAD.title,
    ...Object.values(BEAT_COPY).flatMap((beat) => [beat.label, beat.title, beat.text]),
    FILES_HEAD, OPEN_WORKSPACE, BEND_NOTE, TURN_HINT, wing.field?.label ?? "",
    ...wingFacts(wing, material).flat(), ...wingParts(wing).flat(), ...(result ? [result.first, result.when] : []),
  ];
}
