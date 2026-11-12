/**
 * Which field the viewer shows and the values behind it (ADR-0051, faces and bending since ADR-0053): a list of the fields the package
 * wrote, and for the chosen one its values per element (the result) or per node (the display average the package wrote), with its unit
 * and its words. A shell solve carries both faces of every ply, bottom then top, and the deflection, rotations, curvatures, moments and
 * transverse shear forces; a membrane solve carries one value per ply. The range of the chosen field is the package's too (ADR-0063).
 * Nothing is computed here beyond picking arrays the fea package wrote.
 */
import type { Faced, Fields } from "./studio-api";

export type FieldOption = {
  id: string; label: string; unit: string; group: string;
  perPly?: boolean; perFace?: boolean; perCriterion?: boolean; signed: boolean; nodalOnly?: boolean;
  /** element values only: no display averages written (ADR-0066 amendment 2), so the averaging switch does not apply */
  elementOnly?: boolean;
};
export type FieldChoice = { id: string; ply: number; face?: number; criterion: string; averaged: boolean }; // face: 0 bottom, 1 top, when the package wrote faces
export type FieldValues = { values: (number | null)[]; by: "node" | "element"; label: string; unit: string; signed: boolean;
  /** The ends the package wrote for what is shown, or null for a job solved before the package wrote ranges. */
  range: [number, number] | null };

const STRESS = ["S11", "S22", "S12"] as const;

/** Whether the package wrote both faces of every ply (a shell solve). */
export function hasFaces(fields: Fields): boolean {
  return Array.isArray(fields.mesh.faces) && fields.mesh.faces.length > 0;
}

/** One ply's value from what the package wrote: the value itself, or the chosen face's when the package wrote both faces. */
export function onFace<T>(fields: Fields, value: Faced<T>, face: number): T {
  if (!hasFaces(fields)) return value as T;
  const faces = value as T[];
  return faces[Math.min(Math.max(face, 0), faces.length - 1)];
}

/** The larger of a ply's face values (a failure index), or the value itself. */
export function worstFace(fields: Fields, value: Faced<number | null>): number | null {
  if (!hasFaces(fields)) return value as number | null;
  const finite = (value as (number | null)[]).filter((v): v is number => v !== null);
  return finite.length ? Math.max(...finite) : null;
}

export function fieldOptions(fields: Fields): FieldOption[] {
  const lab = fields.labels;
  const shell = (fields.mesh.translations ?? 2) === 3;
  const faces = hasFaces(fields);
  const options: FieldOption[] = [
    { id: "u_mag", label: "Displacement |u|", unit: lab.length, group: "Displacement", signed: false, nodalOnly: true },
    { id: "u_x", label: "Displacement u (x)", unit: lab.length, group: "Displacement", signed: true, nodalOnly: true },
    { id: "u_y", label: "Displacement v (y)", unit: lab.length, group: "Displacement", signed: true, nodalOnly: true },
  ];
  if (shell) {
    options.push({ id: "u_z", label: "Deflection w (z)", unit: lab.length, group: "Displacement", signed: true, nodalOnly: true });
    options.push({ id: "theta_x", label: "Rotation about x", unit: lab.rotation ?? "rad", group: "Rotation", signed: true, nodalOnly: true });
    options.push({ id: "theta_y", label: "Rotation about y", unit: lab.rotation ?? "rad", group: "Rotation", signed: true, nodalOnly: true });
  }
  options.push(
    { id: "eps_x", label: "Membrane strain eps_x", unit: "-", group: "Strain", signed: true },
    { id: "eps_y", label: "Membrane strain eps_y", unit: "-", group: "Strain", signed: true },
    { id: "gamma_xy", label: "Membrane shear strain gamma_xy", unit: "-", group: "Strain", signed: true },
    { id: "N_x", label: "Section force N_x", unit: lab.force_per_length, group: "Section force", signed: true },
    { id: "N_y", label: "Section force N_y", unit: lab.force_per_length, group: "Section force", signed: true },
    { id: "N_xy", label: "Section force N_xy", unit: lab.force_per_length, group: "Section force", signed: true },
  );
  if (shell) {
    options.push(
      { id: "kappa_x", label: "Curvature kappa_x", unit: lab.per_length ?? `1/${lab.length}`, group: "Curvature", signed: true },
      { id: "kappa_y", label: "Curvature kappa_y (along the coupon)", unit: lab.per_length ?? `1/${lab.length}`, group: "Curvature", signed: true },
      { id: "kappa_xy", label: "Twist kappa_xy", unit: lab.per_length ?? `1/${lab.length}`, group: "Curvature", signed: true },
      { id: "M_x", label: "Moment M_x", unit: lab.moment ?? lab.force, group: "Moment", signed: true },
      { id: "M_y", label: "Moment M_y (along the coupon)", unit: lab.moment ?? lab.force, group: "Moment", signed: true },
      { id: "M_xy", label: "Twisting moment M_xy", unit: lab.moment ?? lab.force, group: "Moment", signed: true },
      { id: "Q_x", label: "Transverse shear force Q_x", unit: lab.force_per_length, group: "Shear force", signed: true },
      { id: "Q_y", label: "Transverse shear force Q_y", unit: lab.force_per_length, group: "Shear force", signed: true },
    );
  }
  options.push(
    { id: "S11", label: "Ply stress S11 (along the fibres)", unit: lab.stress, group: "Ply stress", perPly: true, perFace: faces, signed: true },
    { id: "S22", label: "Ply stress S22 (across the fibres)", unit: lab.stress, group: "Ply stress", perPly: true, perFace: faces, signed: true },
    { id: "S12", label: "Ply shear stress S12", unit: lab.stress, group: "Ply stress", perPly: true, perFace: faces, signed: true },
    { id: "mises", label: "Ply von Mises stress", unit: lab.stress, group: "Ply stress", perPly: true, perFace: faces, signed: false },
  );
  if (fields.element.ply.invariants) { // what Abaqus prints beside Mises (ADR-0066 amendment 2): element values, no display averages
    for (const [id, label, signed] of INVARIANT_OPTIONS) {
      options.push({ id, label, unit: lab.stress, group: "Ply stress", perPly: true, perFace: faces, signed, elementOnly: true });
    }
  }
  options.push(
    { id: "E11", label: "Ply strain E11 (along the fibres)", unit: "-", group: "Ply strain", perPly: true, perFace: faces, signed: true, elementOnly: true },
    { id: "E22", label: "Ply strain E22 (across the fibres)", unit: "-", group: "Ply strain", perPly: true, perFace: faces, signed: true, elementOnly: true },
    { id: "E12", label: "Ply shear strain E12 (engineering)", unit: "-", group: "Ply strain", perPly: true, perFace: faces, signed: true, elementOnly: true },
  );
  if (Object.keys(fields.element.failure).length) {
    options.push({ id: "failure_index", label: "Failure index 1/R, worst ply", unit: "-", group: "Failure", perCriterion: true, signed: false });
    options.push({ id: "failure_index_ply", label: faces ? "Failure index 1/R of one ply, worse face" : "Failure index 1/R of one ply", unit: "-", group: "Failure",
      perCriterion: true, perPly: true, signed: false });
  }
  return options;
}

export const DEFAULT_CHOICE = (fields: Fields): FieldChoice => ({
  id: Object.keys(fields.element.failure).length ? "failure_index" : (fields.mesh.translations ?? 2) === 3 ? "u_z" : "eps_y", ply: 1, face: 0,
  // the answer's earliest criterion (ADR-0085), the gauge section's on a gripped coupon; the whole model's on an older job
  criterion: fields.summary.verdict?.earliest ?? fields.summary.earliest ?? Object.keys(fields.element.failure)[0] ?? "", averaged: true,
});

/** The values of the chosen field: per node when averaged (or nodal by nature), else per element; with the range the package wrote for them. */
export function valuesFor(fields: Fields, choice: FieldChoice): FieldValues {
  const picked = pickValues(fields, choice);
  return { ...picked, range: rangeFor(fields, choice, picked.by) };
}

/** The ends the package wrote for the chosen field as shown: element values or display averages, the chosen ply and face, the chosen
 * criterion (ADR-0063). Null when the package wrote none (a job solved before ranges were written) or neither end is finite. */
export function rangeFor(fields: Fields, choice: FieldChoice, by: "node" | "element"): [number, number] | null {
  const ranges = fields.ranges;
  if (!ranges) return null;
  const option = fieldOptions(fields).find((o) => o.id === choice.id) ?? fieldOptions(fields)[0];
  const k = Math.min(Math.max(choice.ply, 1), fields.mesh.plies) - 1;
  const face = Math.min(Math.max(choice.face ?? 0, 0), 1);
  const criterion = fields.element.failure[choice.criterion] ? choice.criterion : Object.keys(fields.element.failure)[0];
  const table = option.perCriterion ? (ranges[option.id]?.[criterion] as Record<string, unknown> | undefined) : ranges[option.id];
  let entry: unknown = table?.[by === "node" ? "nodal" : "element"];
  if (option.perPly && Array.isArray(entry)) {
    entry = entry[k];
    if (option.perFace && hasFaces(fields) && Array.isArray(entry) && Array.isArray(entry[0])) entry = entry[face];
  }
  return Array.isArray(entry) && entry.length === 2 && typeof entry[0] === "number" && typeof entry[1] === "number" ? [entry[0], entry[1]] : null;
}

function pickValues(fields: Fields, choice: FieldChoice): Omit<FieldValues, "range"> {
  const option = fieldOptions(fields).find((o) => o.id === choice.id) ?? fieldOptions(fields)[0];
  const k = Math.min(Math.max(choice.ply, 1), fields.mesh.plies) - 1;
  const face = Math.min(Math.max(choice.face ?? 0, 0), 1);
  const criterion = fields.element.failure[choice.criterion] ? choice.criterion : Object.keys(fields.element.failure)[0];
  const faceWord = option.perFace && hasFaces(fields) ? `, ${fields.mesh.faces![face]} face` : "";
  const plyWord = option.perPly ? ` (ply ${k + 1}, ${fields.mesh.angles[k]}°${faceWord})` : "";
  const critWord = option.perCriterion ? ` by ${criterion.replace("_", " ")}` : "";
  const label = `${option.label}${plyWord}${critWord}`;
  const nodal = (values: (number | null)[]): Omit<FieldValues, "range"> => ({ values, by: "node", label, unit: option.unit, signed: option.signed });
  const element = (values: (number | null)[]): Omit<FieldValues, "range"> => ({ values, by: "element", label, unit: option.unit, signed: option.signed });
  const n = fields.nodal, e = fields.element;
  const column = (rows: (number | null)[][] | undefined, i: number): (number | null)[] => (rows ?? []).map((row) => row[i]);
  switch (option.id) {
    case "u_mag": return nodal(n.magnitude);
    case "u_x": return nodal(n.displacement.map((u) => u[0]));
    case "u_y": return nodal(n.displacement.map((u) => u[1]));
    case "u_z": return nodal(n.displacement.map((u) => u[2] ?? 0));
    case "theta_x": return nodal(column(n.rotation, 0));
    case "theta_y": return nodal(column(n.rotation, 1));
    case "eps_x": case "eps_y": case "gamma_xy": {
      const i = ["eps_x", "eps_y", "gamma_xy"].indexOf(option.id);
      return choice.averaged ? nodal(column(n.averages.strain, i)) : element(column(e.strain, i));
    }
    case "N_x": case "N_y": case "N_xy": {
      const i = ["N_x", "N_y", "N_xy"].indexOf(option.id);
      return choice.averaged ? nodal(column(n.averages.section_force, i)) : element(column(e.section_force, i));
    }
    case "kappa_x": case "kappa_y": case "kappa_xy": {
      const i = ["kappa_x", "kappa_y", "kappa_xy"].indexOf(option.id);
      return choice.averaged && n.averages.curvature ? nodal(column(n.averages.curvature, i)) : element(column(e.curvature, i));
    }
    case "M_x": case "M_y": case "M_xy": {
      const i = ["M_x", "M_y", "M_xy"].indexOf(option.id);
      return choice.averaged && n.averages.moment ? nodal(column(n.averages.moment, i)) : element(column(e.moment, i));
    }
    case "Q_x": case "Q_y": {
      const i = ["Q_x", "Q_y"].indexOf(option.id);
      return choice.averaged && n.averages.shear_force ? nodal(column(n.averages.shear_force, i)) : element(column(e.shear_force, i));
    }
    case "S11": case "S22": case "S12": {
      const i = STRESS.indexOf(option.id);
      return choice.averaged
        ? nodal(n.averages.ply_stress_12.map((plies) => onFace(fields, plies[k], face)[i]))
        : element(e.ply.stress_12.map((plies) => onFace(fields, plies[k], face)[i]));
    }
    case "tresca": case "max_principal": case "mid_principal": case "min_principal": case "pressure":
      return element((e.ply.invariants?.[option.id] ?? []).map((plies) => onFace(fields, plies[k], face)));
    case "E11": case "E22": case "E12": {
      const i = ["E11", "E22", "E12"].indexOf(option.id);
      return element(e.ply.strain_12.map((plies) => onFace(fields, plies[k], face)[i]));
    }
    case "mises": return choice.averaged
      ? nodal(n.averages.ply_mises.map((plies) => onFace(fields, plies[k], face)))
      : element(e.ply.mises.map((plies) => onFace(fields, plies[k], face)));
    case "failure_index": return choice.averaged && n.averages.failure_index[criterion]
      ? nodal(n.averages.failure_index[criterion]) : element(e.failure[criterion].element_index);
    case "failure_index_ply": return element(e.failure[criterion].index.map((plies) => worstFace(fields, plies[k])));
    default: return element(column(e.strain, 1));
  }
}

export type Readout = { title: string; rows: [string, string][] };

/** Tresca, the principal stresses and the pressure, with the names Abaqus/CAE gives them under S (ADR-0066 amendment 2): comparison
 * quantities, not a composite's failure criterion. */
export const INVARIANT_OPTIONS: [string, string, boolean][] = [
  ["tresca", "Ply Tresca stress (S, Tresca)", false],
  ["max_principal", "Ply max. principal stress (S, Max. Principal)", true],
  ["mid_principal", "Ply mid. principal stress (S, Mid. Principal)", true],
  ["min_principal", "Ply min. principal stress (S, Min. Principal)", true],
  ["pressure", "Ply pressure (S, Pressure)", true],
];

/** The columns of the probe table, as Abaqus/CAE names them: the stresses in each ply's material axes, the invariants, the strains. */
export const PROBE_COLUMNS = ["S11", "S22", "S12", "Mises", "Tresca", "Max. Principal", "Mid. Principal", "Min. Principal", "Pressure", "E11", "E22", "E12"];

export type ProbeRow = { ply: number; angle: number; face: string | null; values: (number | null)[] };
export type ProbeTable = { element: string; instance: string; label: string; centroid: [number, number]; rows: ProbeRow[]; note: string };

/** Every ply of one element as Abaqus/CAE's Query > Probe Values shows it for a composite shell: the element's own number in its
 * instance, the centroid's value (no averaging), each ply in its material axes, S11 S22 S12, Mises, Tresca, the principal stresses, the
 * pressure and the strains. A membrane coupon has one value per ply, the same at the ply's bottom, middle and top section points; a
 * bending coupon has its two faces. S13 and S23 are not modelled by the membrane kernel and are not shown as numbers. */
export function probeTable(fields: Fields, element: number): ProbeTable {
  const e = fields.element;
  const [instance, label] = (() => {
    const full = fields.mesh.element_labels[element];
    const dot = full.lastIndexOf(".");
    return dot >= 0 ? [full.slice(0, dot), full.slice(dot + 1)] : ["", full];
  })();
  const faces = hasFaces(fields) ? fields.mesh.faces! : [null];
  const rows: ProbeRow[] = [];
  for (let k = 0; k < fields.mesh.plies; k += 1) {
    faces.forEach((faceName, f) => {
      const stress = onFace(fields, e.ply.stress_12[element][k], f);
      const strain = onFace(fields, e.ply.strain_12[element][k], f);
      const invariant = (name: string): number | null => (e.ply.invariants?.[name] ? onFace(fields, e.ply.invariants[name][element][k], f) : null);
      rows.push({ ply: k + 1, angle: fields.mesh.angles[k], face: faceName, values: [
        stress[0], stress[1], stress[2], onFace(fields, e.ply.mises[element][k], f),
        invariant("tresca"), invariant("max_principal"), invariant("mid_principal"), invariant("min_principal"), invariant("pressure"),
        strain[0], strain[1], strain[2],
      ] });
    });
  }
  const note = hasFaces(fields)
    ? "Element centroid, no averaging, each ply in its material axes, at its bottom and top faces."
    : "Element centroid, no averaging, each ply in its material axes; the membrane state is the same at a ply's bottom, middle and top "
      + "section points. S13 and S23 are not modelled (membrane state). In Abaqus/CAE: Query > Probe Values, the element by its number, "
      + "averaging off, the ply's section point.";
  return { element: fields.mesh.element_labels[element], instance, label, centroid: [e.centroids[element][0], e.centroids[element][1]], rows, note };
}

/** The probe table as a CSV, the columns in Abaqus/CAE's words with the units, the numbers as the package wrote them. */
export function probeCsv(fields: Fields, table: ProbeTable): string {
  const lab = fields.labels;
  const head = ["Element", "Ply", "Angle (deg)", ...(table.rows.some((r) => r.face) ? ["Face"] : []),
    ...PROBE_COLUMNS.map((c, i) => `${c} (${i < 9 ? lab.stress : "-"})`)];
  const cell = (v: number | null) => (v === null || v === undefined ? "" : String(v));
  const lines = table.rows.map((r) => [table.element, String(r.ply), String(r.angle), ...(r.face ? [r.face] : []), ...r.values.map(cell)].join(","));
  return [head.join(","), ...lines].join("\n") + "\n";
}

/** What one element holds, for the readout beside the picked element: its strains, section forces (and, when it bends, its curvatures,
 * moments and shear forces), and the chosen ply's stresses and ratio, on the chosen face when the package wrote faces. */
export function elementReadout(fields: Fields, element: number, choice: FieldChoice, print: (v: number | null) => string): Readout {
  const lab = fields.labels, e = fields.element;
  const k = Math.min(Math.max(choice.ply, 1), fields.mesh.plies) - 1;
  const face = Math.min(Math.max(choice.face ?? 0, 0), 1);
  const faces = hasFaces(fields);
  const plyName = `Ply ${k + 1} (${fields.mesh.angles[k]}°)${faces ? `, ${fields.mesh.faces![face]} face` : ""}`;
  const rows: [string, string][] = [
    ["Centroid (x, y)", `${print(e.centroids[element][0])}, ${print(e.centroids[element][1])} ${lab.length}`],
    ["eps_x, eps_y, gamma_xy", e.strain[element].map(print).join(", ")],
    [`N_x, N_y, N_xy (${lab.force_per_length})`, e.section_force[element].map(print).join(", ")],
  ];
  if (e.curvature && e.moment && e.shear_force) {
    rows.push([`kappa_x, kappa_y, kappa_xy (${lab.per_length ?? `1/${lab.length}`})`, e.curvature[element].map(print).join(", ")]);
    rows.push([`M_x, M_y, M_xy (${lab.moment ?? lab.force})`, e.moment[element].map(print).join(", ")]);
    rows.push([`Q_x, Q_y (${lab.force_per_length})`, e.shear_force[element].map(print).join(", ")]);
  }
  rows.push([`${plyName} S11, S22, S12 (${lab.stress})`, onFace(fields, e.ply.stress_12[element][k], face).map(print).join(", ")]);
  rows.push([`${plyName} von Mises (${lab.stress})`, print(onFace(fields, e.ply.mises[element][k], face))]);
  for (const [criterion, failure] of Object.entries(e.failure)) {
    const ratio = onFace(fields, failure.ratio[element][k], face);
    const index = onFace(fields, failure.index[element][k], face);
    const mode = onFace(fields, failure.mode[element][k], face);
    rows.push([`${criterion.replace("_", " ")}: ply ${k + 1}${faces ? ` ${fields.mesh.faces![face]} face` : ""} R, 1/R, mode`,
      `${print(ratio)}, ${print(index)}, ${e.modes[mode]}`]);
    const worst = failure.worst_face ? ` (${failure.worst_face[element]} face)` : "";
    rows.push([`${criterion.replace("_", " ")}: worst ply of the element`, `ply ${failure.worst_ply[element]}${worst}, 1/R = ${print(failure.element_index[element])}`]);
  }
  return { title: `Element ${fields.mesh.element_labels[element].split(".").pop()}`, rows };
}
