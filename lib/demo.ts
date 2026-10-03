import Papa from "papaparse";

export const sampleCSV = `coupon_id,panel_id,material_id,test_standard,layup,n_plies,thickness_mm,width_mm,hole_d_mm,failure_load_kN,failure_stress_MPa,modulus_GPa,failure_mode
DEMO-001,P-DEMO,CF-EP-01,D3039,[45/-45/0/90]2s,16,2.08,25,0,48.2,927,54.1,LGM
DEMO-002,P-DEMO,CF-EP-01,D3039,[45/-45/0/90]2s,16,2.09,25,0,47.6,911,53.8,LGM
DEMO-003,P-DEMO,CF-EP-01,D5766,[45/-45/0/90]2s,16,2.08,36,6,39.4,526,52.9,LGM`;

export type TestRow = Record<string, string>;
export type Dataset = {
  rows: TestRow[];
  errors: string[];
  name: string;
  example: boolean;
};
const required = [
  "coupon_id",
  "panel_id",
  "material_id",
  "test_standard",
  "layup",
  "n_plies",
  "thickness_mm",
  "width_mm",
  "hole_d_mm",
  "failure_load_kN",
  "failure_stress_MPa",
  "modulus_GPa",
  "failure_mode",
];
export function parseDataset(
  text: string,
  name: string,
  example = false,
): Dataset {
  const parsed = Papa.parse<TestRow>(text, {
    header: true,
    skipEmptyLines: "greedy",
    transformHeader: (h) => h.replace(/^\uFEFF/, "").trim(),
    transform: (v) => v.trim(),
  });
  const errors = parsed.errors.map((e) => `CSV: ${e.message}`);
  const missing = required.filter((k) => !parsed.meta.fields?.includes(k));
  if (missing.length) errors.push(`Missing columns: ${missing.join(", ")}`);
  if (!parsed.data.length) errors.push("The file has no coupon records.");
  if (parsed.data.length > 5000)
    errors.push("This preview supports up to 5,000 records.");
  const ids = new Set<string>();
  parsed.data.slice(0, 5000).forEach((row, i) => {
    const prefix = `Row ${i + 2}`;
    for (const k of required)
      if (!row[k]) errors.push(`${prefix}: ${k} is required.`);
    if (ids.has(row.coupon_id))
      errors.push(`${prefix}: duplicate coupon ID ${row.coupon_id}.`);
    ids.add(row.coupon_id);
    for (const k of [
      "n_plies",
      "thickness_mm",
      "width_mm",
      "failure_load_kN",
      "failure_stress_MPa",
      "modulus_GPa",
    ]) {
      if (row[k] && (!Number.isFinite(Number(row[k])) || Number(row[k]) <= 0))
        errors.push(`${prefix}: ${k} must be a positive number.`);
    }
    if (row.n_plies && !Number.isInteger(Number(row.n_plies)))
      errors.push(`${prefix}: n_plies must be an integer.`);
    const hole = Number(row.hole_d_mm);
    if (row.hole_d_mm && (!Number.isFinite(hole) || hole < 0))
      errors.push(`${prefix}: hole_d_mm must be zero or positive.`);
    if (!["D3039", "D5766"].includes(row.test_standard))
      errors.push(
        `${prefix}: use D3039 or D5766 for this first-phase preview.`,
      );
    if (row.test_standard === "D3039" && hole !== 0)
      errors.push(`${prefix}: unnotched tension requires hole_d_mm = 0.`);
    if (
      row.test_standard === "D5766" &&
      !(hole > 0 && hole < Number(row.width_mm))
    )
      errors.push(
        `${prefix}: open-hole diameter must be positive and less than width.`,
      );
  });
  return { rows: parsed.data.slice(0, 5000), errors, name, example };
}

export type Scope = {
  objective: string;
  test_standard: string | null;
  material: string | null;
  width_mm: number | null;
  length_mm: number | null;
  thickness_mm: number | null;
  hole_diameter_mm: number | null;
  ply_count: number | null;
  layup: string | null;
  allowed_angles: string | null;
  boundary_conditions: string | null;
  environment: string | null;
  applied_load_kN: number | null;
  safety_factor: number | null;
  status: string;
};
export const emptyScope: Scope = {
  objective: "Minimize mass subject to verified margins",
  test_standard: null,
  material: null,
  width_mm: null,
  length_mm: null,
  thickness_mm: null,
  hole_diameter_mm: null,
  ply_count: null,
  layup: null,
  allowed_angles: null,
  boundary_conditions: null,
  environment: null,
  applied_load_kN: null,
  safety_factor: null,
  status: "Draft — requires engineering review",
};
export type Reply = {
  kind:
    | "brief"
    | "table"
    | "checklist"
    | "json"
    | "overview"
    | "deliverables"
    | "report";
  scope: Scope;
  prompt: string;
};
export function makeReply(prompt: string, previous: Scope): Reply {
  const p = prompt.toLowerCase().replace(/\u2212/g, "-");
  const scope = { ...previous };
  if (!/compare|comparison|difference/.test(p)) {
    if (/d5766|open[- ]hole|notched/.test(p) && !/unnotched/.test(p))
      scope.test_standard = "ASTM D5766";
    if (/d3039|unnotched/.test(p)) scope.test_standard = "ASTM D3039";
  }
  if (/carbon|cf-ep/.test(p))
    scope.material = "Carbon / epoxy — material system to confirm";
  if (/glass/.test(p))
    scope.material = "Glass / epoxy — future material system";
  if (/aramid/.test(p))
    scope.material = "Aramid / epoxy — future material system";
  if (/\bpla\b|printed polymer/.test(p))
    scope.material = "Printed polymer — research context, outside laminate MVP";
  if (/maximi[sz]e strength/.test(p))
    scope.objective = "Maximize strength at fixed thickness";
  // Capture the complete signed number. The boundary prevents matching just the
  // positive tail of a negative, decimal or exponent-form input.
  const signedNumber = String.raw`([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)`;
  const number = String.raw`(?<![\w.+-])${signedNumber}`;
  const separator = String.raw`\s*(?:x|×|by)\s*`;
  const volume = p.match(new RegExp(`${number}${separator}${signedNumber}${separator}${signedNumber}\\s*mm\\b`));
  const dimensions = p.match(new RegExp(`${number}${separator}${signedNumber}\\s*mm\\b`));
  if (volume) {
    scope.length_mm = Number(volume[1]);
    scope.width_mm = Number(volume[2]);
    scope.thickness_mm = Number(volume[3]);
  } else if (dimensions) {
    scope.length_mm = Number(dimensions[1]);
    scope.width_mm = Number(dimensions[2]);
  }
  for (const [key, pattern] of [
    ["width_mm", new RegExp(`\\bwidth\\s*(?:of|=|:)?\\s*${number}\\s*mm\\b`)],
    ["width_mm", new RegExp(`${number}\\s*mm\\s*wide\\b`)],
    ["length_mm", new RegExp(`\\blength\\s*(?:of|=|:)?\\s*${number}\\s*mm\\b`)],
    ["applied_load_kN", new RegExp(`${number}\\s*kn\\b`)],
    [
      "safety_factor",
      new RegExp(`\\b(?:safety factor|factor of safety|fs)\\s*(?:of|=|:)?\\s*${number}`),
    ],
    ["thickness_mm", new RegExp(`\\bthickness\\s*(?:of|=|:)?\\s*${number}\\s*mm\\b`)],
    ["thickness_mm", new RegExp(`${number}\\s*mm\\s*thick`)],
    [
      "hole_diameter_mm",
      new RegExp(`\\bhole(?: diameter)?\\s*(?:of|=|:)?\\s*${number}\\s*mm\\b`),
    ],
    ["hole_diameter_mm", new RegExp(`${number}\\s*mm\\s*hole\\b`)],
    ["ply_count", new RegExp(`${number}\\s*plies\\b`)],
  ] as const) {
    const match = p.match(pattern);
    if (match) scope[key] = Number(match[1]);
  }
  if (scope.test_standard === "ASTM D3039" && scope.hole_diameter_mm === null)
    scope.hole_diameter_mm = 0;
  const layup = prompt.match(/\[[\d\s+\-/°.]+\](?:\d+)?s?/i);
  if (layup) scope.layup = layup[0];
  const angles = prompt.match(
    /(?:allowed angles|angles)\s*(?:are|:|=)?\s*([\d+\-±°, /]+)/i,
  );
  if (angles) scope.allowed_angles = angles[1].trim();
  if (/clamped|fixed grip|fixed end/.test(p))
    scope.boundary_conditions =
      "One grip fixed; opposite grip loaded — confirm restraint details";
  const boundary = prompt.match(
    /(?:boundary conditions|restraints)\s*[:=]\s*([^;\n]+)/i,
  );
  if (boundary) scope.boundary_conditions = boundary[1].trim();
  if (/room temp|ambient|\brtd\b/.test(p))
    scope.environment = "Room-temperature dry — exact conditions to confirm";
  const environment = prompt.match(
    /(?:environment|conditioning)\s*[:=]\s*([^;\n]+)/i,
  );
  if (environment) scope.environment = environment[1].trim();
  let kind: Reply["kind"] = "brief";
  if (/compare|comparison|table|difference/.test(p)) kind = "table";
  else if (/json|structured/.test(p)) kind = "json";
  else if (/latex|report|document.*physics/.test(p)) kind = "report";
  else if (
    /\bfea\b|\bstress\b|\bstrain\b|failure|where.*fail|\bcad\b|output|deliverable/.test(
      p,
    )
  )
    kind = "deliverables";
  else if (/checklist|upload|submit|csv|test data/.test(p)) kind = "checklist";
  else if (/what is|overview|about|how does|roadmap|vision/.test(p))
    kind = "overview";
  return { kind, scope, prompt };
}

export function scopeQuestions(scope: Scope): string[] {
  return [
    !scope.test_standard &&
      "Is this an unnotched (D3039) or open-hole (D5766) tension coupon?",
    !scope.material &&
      "Which material system and approved property source should we use?",
    (!scope.length_mm || !scope.width_mm) &&
      "What are the length and width? For example, “250 × 36 mm”.",
    !scope.thickness_mm && "What is the total laminate thickness, in mm?",
    scope.test_standard === "ASTM D5766" &&
      !scope.hole_diameter_mm &&
      "What is the open-hole diameter, in mm?",
    !scope.applied_load_kN && "What load should be applied, in kN?",
    (!scope.ply_count || !scope.layup) &&
      "What are the ply count and stacking sequence? For example, “16 plies, [45/-45/0/90]2s”.",
    !scope.allowed_angles &&
      "Which ply angles are allowed during optimization?",
    !scope.boundary_conditions &&
      "How is the specimen constrained and loaded at the grips?",
    !scope.environment &&
      "What temperature and conditioning should the analysis represent?",
    !scope.safety_factor && "What factor of safety is required?",
  ].filter((question): question is string => Boolean(question));
}

export function scopeErrors(scope: Scope): string[] {
  const errors: string[] = [];
  for (const key of [
    "length_mm",
    "width_mm",
    "thickness_mm",
    "applied_load_kN",
    "safety_factor",
    "ply_count",
  ] as const) {
    const n = scope[key];
    if (n !== null && (!Number.isFinite(n) || n <= 0))
      errors.push(`${key} must be positive.`);
  }
  if (scope.ply_count !== null && !Number.isInteger(scope.ply_count))
    errors.push("Ply count must be a whole number.");
  if (scope.safety_factor !== null && scope.safety_factor < 1)
    errors.push("Use a safety factor of at least 1 for this preview.");
  if (
    scope.hole_diameter_mm !== null &&
    (!Number.isFinite(scope.hole_diameter_mm) || scope.hole_diameter_mm < 0)
  )
    errors.push("Hole diameter must be zero or positive.");
  if (
    scope.test_standard === "ASTM D5766" &&
    scope.hole_diameter_mm !== null &&
    scope.hole_diameter_mm <= 0
  )
    errors.push("An open-hole coupon needs a positive hole diameter.");
  if (scope.test_standard === "ASTM D3039" && scope.hole_diameter_mm)
    errors.push("An unnotched coupon must have zero hole diameter.");
  if (
    scope.width_mm &&
    scope.hole_diameter_mm !== null &&
    scope.hole_diameter_mm >= scope.width_mm
  )
    errors.push("Hole diameter must be less than coupon width.");
  return errors;
}

export function latexReport(scope: Scope): string {
  const escape = (text: string) =>
    text.replace(
      /[\\{}$&#%_^~]/g,
      (c) =>
        ({
          "\\": "\\textbackslash{}",
          "{": "\\{",
          "}": "\\}",
          $: "\\$",
          "&": "\\&",
          "#": "\\#",
          "%": "\\%",
          _: "\\_",
          "^": "\\textasciicircum{}",
          "~": "\\textasciitilde{}",
        })[c]!,
    );
  const rows = Object.entries(scope)
    .map(
      ([key, value]) =>
        `${escape(key)} & ${escape(String(value ?? "Not specified"))} \\\\`,
    )
    .join("\n");
  return String.raw`\documentclass{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,longtable,hyperref}
\title{Anisotropy AI: Analysis Report Outline}
\date{Product preview -- no analysis results}
\begin{document}
\maketitle
\textbf{Draft template only. No engineering conclusions or numerical results have been calculated.}
\section{Problem definition and user-supplied inputs}
\begin{longtable}{p{0.30\textwidth}p{0.60\textwidth}}
${rows}
\end{longtable}
\section{Material basis and provenance}
Pending: approved property records, units, test IDs, conditioning, and statistical basis.
\section{Geometry and boundary conditions}
Pending: reviewed CAD definition, coordinate system, load introduction, restraints, and modeling assumptions.
\section{Physics and governing equations}
Planned Classical Laminate Theory under its applicable assumptions:
\[
\begin{bmatrix}N\\M\end{bmatrix}=
\begin{bmatrix}A&B\\B&D\end{bmatrix}
\begin{bmatrix}\varepsilon^0\\\kappa\end{bmatrix}.
\]
Planned margin convention: $MS=R/FS-1$, with strength ratio $R$ supplied by verified calculations.
Document ply stress recovery, applicable maximum-stress, Tsai--Wu, and Hashin criteria, and limits of each method. No criterion has been evaluated in this preview.
\section{Mesh and solver verification}
Pending: element selection, convergence study, solver version, and independent cross-checks.
\section{Stress, strain, and failure assessment}
Pending: units, field components, per-ply results, candidate failure locations, mode classification, margins, and uncertainty.
\section{Comparison with physical tests}
Pending: measured response, observed fracture region, held-out evaluation, discrepancies, and limitations.
\section{Conclusions and limitations}
No engineering conclusion is available before reviewed solver results and validation evidence exist.
\section{Reproducibility and references}
Pending: input definitions, material version, mesh settings, analysis revision, source test IDs, and references.
\end{document}
`;
}

export function downloadFile(
  name: string,
  content: string,
  type = "text/plain",
) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
