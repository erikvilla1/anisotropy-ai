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
// The names a customer reads for the template's columns; the CSV keeps its own headers.
const columnTitles: Record<string, string> = {
  coupon_id: "Coupon ID", panel_id: "Panel ID", material_id: "Material ID", test_standard: "Test standard",
  layup: "Layup", n_plies: "Ply count", thickness_mm: "Thickness (mm)", width_mm: "Width (mm)",
  hole_d_mm: "Hole diameter (mm)", failure_load_kN: "Failure load (kN)", failure_stress_MPa: "Failure stress (MPa)",
  modulus_GPa: "Modulus (GPa)", failure_mode: "Failure mode",
};
const title = (key: string) => columnTitles[key] ?? key;

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
  const errors = parsed.errors.map((e) =>
    e.row === undefined
      ? "The file could not be read as a CSV. Check that it has the same columns as the template."
      : `Row ${e.row + 2} could not be read. Check that it has the same columns as the template.`,
  );
  const missing = required.filter((k) => !parsed.meta.fields?.includes(k));
  if (missing.length)
    errors.push(
      `Missing columns: ${missing.map((k) => `${title(k)} (${k})`).join(", ")}. Add them as in the CSV template.`,
    );
  if (!parsed.data.length) errors.push("The file has no coupons.");
  if (parsed.data.length > 5000)
    errors.push("A file can hold up to 5,000 coupons. Split it and check each part.");
  const ids = new Set<string>();
  parsed.data.slice(0, 5000).forEach((row, i) => {
    const prefix = `Row ${i + 2}`;
    for (const k of required)
      if (!row[k]) errors.push(`${prefix}: ${title(k)} is missing.`);
    if (ids.has(row.coupon_id))
      errors.push(`${prefix}: Duplicate coupon ID ${row.coupon_id}; each coupon needs its own ID.`);
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
        errors.push(`${prefix}: ${title(k)} must be a positive number.`);
    }
    if (row.n_plies && !Number.isInteger(Number(row.n_plies)))
      errors.push(`${prefix}: Ply count must be a whole number.`);
    const hole = Number(row.hole_d_mm);
    if (row.hole_d_mm && (!Number.isFinite(hole) || hole < 0))
      errors.push(`${prefix}: Hole diameter must be zero or positive.`);
    if (!["D3039", "D5766"].includes(row.test_standard))
      errors.push(`${prefix}: Use test standard D3039 or D5766.`);
    if (row.test_standard === "D3039" && hole !== 0)
      errors.push(`${prefix}: D3039 unnotched tension needs a hole diameter of 0.`);
    if (
      row.test_standard === "D5766" &&
      !(hole > 0 && hole < Number(row.width_mm))
    )
      errors.push(
        `${prefix}: The open-hole diameter must be positive and less than the width.`,
      );
  });
  return { rows: parsed.data.slice(0, 5000), errors, name, example };
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
