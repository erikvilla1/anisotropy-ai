import { FileText, FlaskConical, Layers3, Sparkles } from "lucide-react";

/** The workflow steps and the roadmap, moved from the home page to About (audit of 2026-10-31, item 7: the home page
 * "reads as an About"). The wording is the home page's as of 2026-11-05; the validation gate no longer quotes a coupon
 * count, which no record backs (docs/brain/voice.md). */
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
    text: "Search candidate layups, evaluate laminate behavior, and cross-check with finite element analysis.",
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

export type RoadmapStage = { number: string; subtitle: string; title: string; text: string; status: string };

export const roadmap: readonly RoadmapStage[] = [
  {
    number: "01",
    subtitle: "The foundation",
    title: "Coupons",
    text: "Unnotched and open-hole tension, compression, shear and bending. A physics pipeline to be validated against blind lab tests.",
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
    title: "Elements & joints",
    text: "Progressive damage, joints, and future repair analysis, developed through relevant element tests.",
    status: "FUTURE EXPLORATION",
  },
  {
    number: "04",
    subtitle: "Scale the insight",
    title: "Panels & structures",
    text: "Carry the verified foundation toward stiffened panels, buckling, and wing optimization.",
    status: "LONG-TERM DIRECTION",
  },
];

export const validationGate =
  "The first gate: blind predictions checked against a first batch of lab coupons, with the acceptance band agreed from real data.";
