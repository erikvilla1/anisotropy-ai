import { test } from "node:test";
import assert from "node:assert/strict";
import { dualUnits, englishStressUnit, printedColumn, printedElsewhere, printedValue, propertyDisplayValue } from "../lib/property-units";
import { curatedMaterials, materialDatasets } from "../lib/curated-materials";
import { materials } from "../lib/materials";
import references from "../lib/published-material-references.json";

test("English and SI displays convert stress, density, thickness and temperature increments", () => {
  const full = { precision: "full" } as const;
  assert.deepEqual(dualUnits("21.3", "Msi", full), { english: "21.3 Msi", si: "146.858 GPa" });
  assert.deepEqual(dualUnits(1, "MPa", full), { english: "145.038 psi", si: "1 MPa" });
  assert.deepEqual(dualUnits(1, "GPa", full), { english: "0.145038 Msi", si: "1 GPa" });
  assert.equal(dualUnits("1", "lb/in³", full).si, "27,679.9 kg/m³");
  assert.equal(dualUnits("1", "lb/ft³", full).si, "16.0185 kg/m³");
  assert.equal(dualUnits("1", "in", full).si, "25.4 mm");
  assert.equal(dualUnits("-0.5", "10⁻⁶/°F", full).si, "−0.9 × 10⁻⁶/K");
  assert.equal(dualUnits("-250", "ksi", full).si, "−1,723.69 MPa");
  assert.deepEqual(dualUnits(".27", "—"), { english: "0.27", si: "0.27" });
});

test("the converted column keeps the printed value's figures, at least three, trailing zeros included", () => {
  // Daniel & Ishai, AS4 / 3501-6: E1 147 GPa, E2 10.3 GPa, F1t 2280 MPa, F2t 57 MPa, F12 76 MPa, density recorded as 1.6 g/cm³ (audit library-4; whether the book prints 1.60 is unchecked).
  assert.deepEqual(dualUnits(147, "GPa"), { english: "21.3 Msi", si: "147 GPa" });
  assert.deepEqual(dualUnits(10.3, "GPa"), { english: "1.49 Msi", si: "10.3 GPa" });
  assert.deepEqual(dualUnits(2280, "MPa"), { english: "331 ksi", si: "2,280 MPa" });
  assert.deepEqual(dualUnits(57, "MPa"), { english: "8.27 ksi", si: "57 MPa" });
  assert.deepEqual(dualUnits(76, "MPa"), { english: "11.0 ksi", si: "76 MPa" });
  assert.deepEqual(dualUnits(6, "GPa"), { english: "0.870 Msi", si: "6 GPa" });
  assert.deepEqual(dualUnits(0.6, "MPa"), { english: "87.0 psi", si: "0.6 MPa" }); // below 1 ksi a stress reads in psi
  assert.deepEqual(dualUnits(48, "kg/m³"), { english: "3.00 lb/ft³", si: "48 kg/m³" });
  assert.deepEqual(dualUnits(1.6, "g/cm³"), { english: "0.0578 lb/in³", si: "1.6 g/cm³" });
  assert.deepEqual(dualUnits(19.09, "Msi"), { english: "19.09 Msi", si: "131.6 GPa" });
  assert.deepEqual(dualUnits(70, "°F"), { english: "70 °F", si: "21.1 °C" });
  assert.deepEqual(dualUnits(32, "°F"), { english: "32 °F", si: "0 °C" }); // a zero has no figures to keep
});

test("the printed column shows the printed figure: its unit and the trailing zeros of a printed string (audit R2-7)", () => {
  // A density printed in g/cm³ stays in g/cm³ in the SI / metric column, which the table tags "as printed".
  assert.equal(dualUnits(1.58, "g/cm³").si, "1.58 g/cm³");
  assert.equal(dualUnits("1.60", "g/cm³").si, "1.60 g/cm³");
  // X840 / Z60, Chen 2015 Table 3.1 and 3.2: 80.0 GPa, 5.10 GPa and 71.0 MPa keep their zeros.
  assert.deepEqual(dualUnits("80.0", "GPa"), { english: "11.6 Msi", si: "80.0 GPa" });
  assert.equal(dualUnits("5.10", "GPa").si, "5.10 GPa");
  assert.deepEqual(dualUnits("71.0", "MPa"), { english: "10.3 ksi", si: "71.0 MPa" });
  assert.equal(dualUnits("80.0", "GPa", { precision: "full" }).si, "80.0 GPa");
  assert.equal(dualUnits("-0.50", "10⁻⁶/K").si, "−0.50 × 10⁻⁶/K");
  // A number has no printed zeros to keep, and a figure past six significant digits is not padded.
  assert.equal(dualUnits(80, "GPa").si, "80 GPa");
  assert.equal(dualUnits("23.1051480", "Msi").english, "23.1051 Msi");
  const x840 = curatedMaterials.find(m => m.id === "x840-z60-pw")!;
  const shown = (key: string) => dualUnits(propertyDisplayValue(x840.properties.find(p => p.key === key)!), x840.properties.find(p => p.key === key)!.unit).si;
  assert.deepEqual(["E1", "G13", "F12", "G12"].map(shown), ["80.0 GPa", "5.10 GPa", "71.0 MPa", "6.48 GPa"]);
  for (const p of curatedMaterials.flatMap(materialDatasets).flatMap(m => m.properties))
    if (p.printedFigures !== undefined) assert.equal(Number(p.printedFigures), p.value, `${p.key}: ${p.printedFigures}`);
});

test("a table reads every MPa row in one English unit, so a nominal and a minimum value never differ in unit", () => {
  // Divinycell H250: compressive strength 7.2 MPa nominal (1.04 ksi) and 6.1 MPa minimum (885 psi); shear strength below 1 ksi.
  const h250 = references.find(r => r.materialId === "divinycell-h250")!.properties;
  const unit = englishStressUnit(h250);
  assert.equal(unit, "psi");
  const row = (key: string) => dualUnits(h250.find(p => p.key === key)!.value, "MPa", { stressUnit: unit }).english;
  assert.equal(row("compression-strength-nominal"), "1,040 psi");
  assert.equal(row("compression-strength-minimum"), "885 psi");
  assert.match(row("compression-modulus-nominal"), / psi$/);
  // A carbon prepreg's strengths are all above 1 ksi: ksi throughout.
  const textbook = curatedMaterials.find(m => m.id === "as4-3501")!.properties.map(p => ({ value: propertyDisplayValue(p), unit: p.unit }));
  assert.equal(englishStressUnit(textbook), "ksi");
  assert.equal(dualUnits(0.6, "MPa", { stressUnit: "ksi" }).english, "0.0870 ksi");
});

test("every dataset's table tags the column it was printed in, and a row printed in the other column says so", () => {
  for (const d of curatedMaterials.flatMap(materialDatasets))
    assert.ok(printedColumn(d.properties.map(p => p.unit)), `${d.datasetId} has no "as printed" column`);
  // NCAMP prints in US units with the density in g/cm³ (audit library-15).
  const ncamp = curatedMaterials.find(m => m.id === "as4-8552")!;
  const column = printedColumn(ncamp.properties.map(p => p.unit));
  assert.equal(column, "english");
  assert.equal(printedElsewhere("g/cm³", column), "printed in metric units");
  assert.equal(printedElsewhere("Msi", column), "");
  assert.equal(printedElsewhere("in", "si"), "printed in English units");
  assert.equal(printedElsewhere("%", column), "");
  assert.equal(printedColumn(["%", "—"]), null);
});

test("a negative value takes the minus sign and a power-of-ten unit reads as a product", () => {
  assert.deepEqual(dualUnits(-0.9, "10⁻⁶/K"), { english: "−0.500 × 10⁻⁶/°F", si: "−0.9 × 10⁻⁶/K" });
  assert.equal(dualUnits(27, "10⁻⁶/K").si, "27 × 10⁻⁶/K");
  assert.equal(dualUnits(-250, "ksi").english, "−250 ksi");
  // The value as printed, on the source page: the book's α₁ for AS4 / 3501-6 (audit library-13).
  assert.equal(printedValue(-0.9, "10⁻⁶/°C"), "−0.9 × 10⁻⁶/°C");
  assert.equal(printedValue(1.9, "g/cm³"), "1.9 g/cm³");
  assert.equal(printedValue(0.63, "—"), "0.63");
  assert.equal(printedValue("-2–-1", "in"), "−2–−1 in");
});

test("ranges are converted at both ends, missing values stay missing, and questionable magnitudes are not corrected", () => {
  assert.deepEqual(dualUnits("45–49", "%"), { english: "45–49 %", si: "45–49 %" });
  assert.equal(dualUnits("1–2", "in").si, "25.4–50.8 mm");
  assert.equal(dualUnits("-2–-1", "in").si, "−50.8–−25.4 mm");
  assert.deepEqual(dualUnits("TBD", "in"), { english: "Not provided", si: "Not provided" });
  assert.equal(dualUnits("-87300", "ksi", { precision: "full" }).si, "−601,912 MPa");
  assert.equal(dualUnits("1", "unknown").si, "Conversion unavailable");
  for (const p of [...materials.flatMap(m => m.properties), ...references.flatMap(r => r.properties)]) {
    const values = dualUnits(p.value, p.unit);
    assert.notEqual(values.english, "Conversion unavailable", `${p.label}: ${p.value} ${p.unit}`);
    assert.notEqual(values.si, "Conversion unavailable", `${p.label}: ${p.value} ${p.unit}`);
  }
});
