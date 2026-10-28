/**
 * Which field the viewer shows and the values behind it (ADR-0051): a list of the fields the package wrote, and for the chosen
 * one its values per element (the result) or per node (the display average the package wrote), with its unit and its words.
 * Nothing is computed here beyond picking arrays the fea package wrote.
 */
import type { Fields } from "./studio-api";

export type FieldOption = {
  id: string; label: string; unit: string; group: string;
  perPly?: boolean; perCriterion?: boolean; signed: boolean; nodalOnly?: boolean;
};
export type FieldChoice = { id: string; ply: number; criterion: string; averaged: boolean };
export type FieldValues = { values: (number | null)[]; by: "node" | "element"; label: string; unit: string; signed: boolean };

const STRESS = ["S11", "S22", "S12"] as const;

export function fieldOptions(fields: Fields): FieldOption[] {
  const lab = fields.labels;
  const options: FieldOption[] = [
    { id: "u_mag", label: "Displacement |u|", unit: lab.length, group: "Displacement", signed: false, nodalOnly: true },
    { id: "u_x", label: "Displacement u (x)", unit: lab.length, group: "Displacement", signed: true, nodalOnly: true },
    { id: "u_y", label: "Displacement v (y)", unit: lab.length, group: "Displacement", signed: true, nodalOnly: true },
    { id: "eps_x", label: "Membrane strain eps_x", unit: "-", group: "Strain", signed: true },
    { id: "eps_y", label: "Membrane strain eps_y", unit: "-", group: "Strain", signed: true },
    { id: "gamma_xy", label: "Membrane shear strain gamma_xy", unit: "-", group: "Strain", signed: true },
    { id: "N_x", label: "Section force N_x", unit: lab.force_per_length, group: "Section force", signed: true },
    { id: "N_y", label: "Section force N_y", unit: lab.force_per_length, group: "Section force", signed: true },
    { id: "N_xy", label: "Section force N_xy", unit: lab.force_per_length, group: "Section force", signed: true },
    { id: "S11", label: "Ply stress S11 (along the fibres)", unit: lab.stress, group: "Ply stress", perPly: true, signed: true },
    { id: "S22", label: "Ply stress S22 (across the fibres)", unit: lab.stress, group: "Ply stress", perPly: true, signed: true },
    { id: "S12", label: "Ply shear stress S12", unit: lab.stress, group: "Ply stress", perPly: true, signed: true },
    { id: "mises", label: "Ply von Mises stress", unit: lab.stress, group: "Ply stress", perPly: true, signed: false },
  ];
  if (Object.keys(fields.element.failure).length) {
    options.push({ id: "failure_index", label: "Failure index 1/R, worst ply", unit: "-", group: "Failure", perCriterion: true, signed: false });
    options.push({ id: "failure_index_ply", label: "Failure index 1/R of one ply", unit: "-", group: "Failure", perCriterion: true, perPly: true, signed: false });
  }
  return options;
}

export const DEFAULT_CHOICE = (fields: Fields): FieldChoice => ({
  id: Object.keys(fields.element.failure).length ? "failure_index" : "eps_y", ply: 1,
  criterion: fields.summary.earliest ?? Object.keys(fields.element.failure)[0] ?? "", averaged: true,
});

/** The values of the chosen field: per node when averaged (or nodal by nature), else per element. */
export function valuesFor(fields: Fields, choice: FieldChoice): FieldValues {
  const option = fieldOptions(fields).find((o) => o.id === choice.id) ?? fieldOptions(fields)[0];
  const k = Math.min(Math.max(choice.ply, 1), fields.mesh.plies) - 1;
  const criterion = fields.element.failure[choice.criterion] ? choice.criterion : Object.keys(fields.element.failure)[0];
  const plyWord = option.perPly ? ` (ply ${k + 1}, ${fields.mesh.angles[k]}°)` : "";
  const critWord = option.perCriterion ? ` by ${criterion.replace("_", " ")}` : "";
  const label = `${option.label}${plyWord}${critWord}`;
  const nodal = (values: (number | null)[]): FieldValues => ({ values, by: "node", label, unit: option.unit, signed: option.signed });
  const element = (values: (number | null)[]): FieldValues => ({ values, by: "element", label, unit: option.unit, signed: option.signed });
  const n = fields.nodal, e = fields.element;
  switch (option.id) {
    case "u_mag": return nodal(n.magnitude);
    case "u_x": return nodal(n.displacement.map((u) => u[0]));
    case "u_y": return nodal(n.displacement.map((u) => u[1]));
    case "eps_x": case "eps_y": case "gamma_xy": {
      const i = ["eps_x", "eps_y", "gamma_xy"].indexOf(option.id);
      return choice.averaged ? nodal(n.averages.strain.map((row) => row[i])) : element(e.strain.map((row) => row[i]));
    }
    case "N_x": case "N_y": case "N_xy": {
      const i = ["N_x", "N_y", "N_xy"].indexOf(option.id);
      return choice.averaged ? nodal(n.averages.section_force.map((row) => row[i])) : element(e.section_force.map((row) => row[i]));
    }
    case "S11": case "S22": case "S12": {
      const i = STRESS.indexOf(option.id);
      return choice.averaged ? nodal(n.averages.ply_stress_12.map((plies) => plies[k][i])) : element(e.ply.stress_12.map((plies) => plies[k][i]));
    }
    case "mises": return choice.averaged ? nodal(n.averages.ply_mises.map((plies) => plies[k])) : element(e.ply.mises.map((plies) => plies[k]));
    case "failure_index": return choice.averaged && n.averages.failure_index[criterion]
      ? nodal(n.averages.failure_index[criterion]) : element(e.failure[criterion].element_index);
    case "failure_index_ply": return element(e.failure[criterion].index.map((plies) => plies[k]));
    default: return element(e.strain.map((row) => row[1]));
  }
}

export type Readout = { title: string; rows: [string, string][] };

/** What one element holds, for the readout beside the picked element: its strains, section forces, and the chosen ply's stresses and ratio. */
export function elementReadout(fields: Fields, element: number, choice: FieldChoice, print: (v: number | null) => string): Readout {
  const lab = fields.labels, e = fields.element;
  const k = Math.min(Math.max(choice.ply, 1), fields.mesh.plies) - 1;
  const rows: [string, string][] = [
    ["Centroid (x, y)", `${print(e.centroids[element][0])}, ${print(e.centroids[element][1])} ${lab.length}`],
    ["eps_x, eps_y, gamma_xy", e.strain[element].map(print).join(", ")],
    [`N_x, N_y, N_xy (${lab.force_per_length})`, e.section_force[element].map(print).join(", ")],
    [`Ply ${k + 1} (${fields.mesh.angles[k]}°) S11, S22, S12 (${lab.stress})`, e.ply.stress_12[element][k].map(print).join(", ")],
    [`Ply ${k + 1} von Mises (${lab.stress})`, print(e.ply.mises[element][k])],
  ];
  for (const [criterion, failure] of Object.entries(e.failure)) {
    const ratio = failure.ratio[element][k];
    rows.push([`${criterion.replace("_", " ")}: ply ${k + 1} R, 1/R, mode`,
      `${print(ratio)}, ${print(failure.index[element][k])}, ${e.modes[failure.mode[element][k]]}`]);
    rows.push([`${criterion.replace("_", " ")}: worst ply of the element`, `ply ${failure.worst_ply[element]}, 1/R = ${print(failure.element_index[element])}`]);
  }
  return { title: `Element ${fields.mesh.element_labels[element].split(".").pop()}`, rows };
}
