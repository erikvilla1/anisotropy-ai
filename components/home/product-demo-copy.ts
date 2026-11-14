/** The product demo's words (ADR-0095), in one place so the unit test can read every one against the product view's banned terms
 * (lib/studio-copy.ts, ADR-0091). The names of the materials, the run's stages and the files are the workspace's own and are
 * imported where they are shown; the numbers are the recorded run's (lib/demo-run.ts). */
import { degrees, kilonewtons, standardName, type DemoRun } from "@/lib/demo-run";
import type { BeatId } from "./product-demo-timeline";

export const DEMO_HEAD = { label: "THE WORKSPACE / ONE COUPON, START TO FINISH", title: "A coupon analysis, set up for you." };

export const BEAT_COPY: Record<BeatId, { label: string; title: string; text: string }> = {
  describe: {
    label: "DESCRIBE",
    title: "Describe the coupon.",
    text: "Pick a material and a test standard, then type the layup. The assistant asks only for what is missing.",
  },
  model: {
    label: "MODEL",
    title: "The model builds itself.",
    text: "The coupon is drawn to the standard's size, gripped and meshed. There is nothing to draw by hand.",
  },
  analysis: {
    label: "ANALYSIS",
    title: "Run the analysis.",
    text: "The solver returns the stress in every ply and names the first ply to fail.",
  },
  report: {
    label: "REPORT",
    title: "It comes with the report.",
    // The About page's sentence, word for word.
    text: "Less time on repetitive setup and documentation, more time optimizing the structure.",
  },
};

export const ASSISTANT = { name: "Coupon assistant", question: "Which material?", standard: "Standard", layup: "Layup, bottom ply first" };
export const FILES_HEAD = "A full run writes";
export const OPEN_WORKSPACE = "Open the workspace";
export const FIELD_LABEL = "Stress along the fibres";

/** The setup's summary, as the workspace's strip names its cells. */
export function summaryCells(run: DemoRun, material: string): [string, string][] {
  const { coupon, summary, units } = run;
  return [
    ["TEST", coupon.test],
    ["MATERIAL", material],
    ["LAYUP", coupon.layup],
    ["SIZE", `${coupon.length} × ${coupon.width} ${units.length}, per ${standardName(run).replace("ASTM ", "")}`],
    ["MESH", `${summary.elements} elements`],
  ];
}

/** What the run found, in two short lines. */
export function resultLines(run: DemoRun): { first: string; when: string } {
  const { first_failure: first, reaction } = run.summary;
  const pull = `${run.coupon.pull} ${run.coupon.pull_unit}`;
  return {
    first: `First ply to fail: ply ${first.ply} (${degrees(first.angle)}), in ${first.mode} ${first.place}.`,
    when: first.fails
      ? `It fails before the ${pull} pull is reached, at ${first.applied.toFixed(2)} ${first.applied_unit} (${kilonewtons(first.reaction)} kN).`
      : `It holds at the ${pull} pull (${kilonewtons(reaction)} kN) and fails at ${first.applied.toFixed(2)} ${first.applied_unit} (${kilonewtons(first.reaction)} kN).`,
  };
}

/** Every fixed sentence the demo shows, for the banned-term check. */
export function everyLine(run: DemoRun, material: string): string[] {
  const result = resultLines(run);
  return [
    DEMO_HEAD.label, DEMO_HEAD.title,
    ...Object.values(BEAT_COPY).flatMap((beat) => [beat.label, beat.title, beat.text]),
    ...Object.values(ASSISTANT), FILES_HEAD, OPEN_WORKSPACE, FIELD_LABEL,
    ...summaryCells(run, material).flat(), result.first, result.when,
  ];
}
