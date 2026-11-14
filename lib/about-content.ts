import { FileText, FlaskConical, Layers3, Sparkles } from "lucide-react";

/** The workflow steps and the roadmap, moved from the home page to About (audit of 2026-10-31, item 7: the home page
 * "reads as an About"). The wording is the home page's as of 2026-11-05; the validation gate no longer quotes a coupon
 * count, which no record backs (docs/brain/voice.md). The audit of 2026-11-12 keeps to what exists: no layup search, the
 * tests still to come listed once (`comingTests`) for About and the finite element page, and the roadmap's later stages
 * shared with that page's Planned cards. */
export const workflowSteps = [
  {
    icon: Layers3,
    title: "Define the coupon",
    text: "Geometry, material, loads, and design constraints. A clear engineering question comes first.",
    tag: "SPECIFICATION",
  },
  {
    icon: Sparkles,
    title: "Analyze with physics",
    text: "Evaluate the laminate with classical laminate theory and cross-check the coupon with finite element analysis.",
    tag: "ANALYSIS WORKFLOW",
  },
  {
    icon: FlaskConical,
    title: "Build. Test. Compare.",
    text: "Fabricate coupons and compare physical measurements against predictions made before the test.",
    tag: "LAB VALIDATION",
  },
  {
    icon: FileText,
    title: "Make it traceable",
    text: "Connect every result to its inputs, analysis record, and source data. Let the evidence guide the next iteration.",
    tag: "DOCUMENTED RESULTS",
  },
] as const;

/** The coupon tests that follow unnotched tension, in the order both pages name them. */
export const comingTests = ["open-hole tension", "compression", "in-plane shear", "bending", "plates"] as const;

/** A list in words, with the serial comma: "a, b, and c". */
export function listed(items: readonly string[]): string {
  if (items.length < 3) return items.join(" and ");
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

export type RoadmapStage = { number: string; subtitle: string; title: string; text: string; status: string };

export const roadmap: readonly RoadmapStage[] = [
  {
    number: "01",
    subtitle: "The foundation",
    title: "Coupons",
    text: `Unnotched tension (ASTM D3039) first, verified output by output against a reference solver; ${listed(comingTests)} follow one test at a time. Each is then checked against blind lab tests.`,
    status: "CURRENT FOCUS",
  },
  {
    number: "02",
    subtitle: "Broaden the evidence",
    title: "More materials and tests",
    text: "More material systems and more test families, with the uncertainty of each result guiding the next tests.",
    status: "AFTER COUPON VALIDATION",
  },
  {
    number: "03",
    subtitle: "Understand the damage",
    title: "Elements and joints",
    text: "Progressive damage, joints, and repair analysis, developed through element tests.",
    status: "FUTURE EXPLORATION",
  },
  {
    number: "04",
    subtitle: "Scale the insight",
    title: "Panels and structures",
    text: "Stiffened panels, buckling, and wing optimization, built on the verified coupon work.",
    status: "LONG-TERM DIRECTION",
  },
];

export const validationGate =
  "Next milestone: blind predictions checked against a first batch of lab coupons, with the acceptance band agreed from real data.";

/** What the model describes today, and what the research is after. */
export const modelSubjects = ["Strength and stiffness", "First-ply failure location"] as const;
export const modelGoals = ["Prediction uncertainty", "Physics–test discrepancy"] as const;
