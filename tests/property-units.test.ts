import { test } from "node:test";
import assert from "node:assert/strict";
import { dualUnits } from "../lib/property-units";
import { materials } from "../lib/materials";
import references from "../lib/published-material-references.json";

test("English and SI displays convert stress, density, thickness and temperature increments", () => {
  assert.deepEqual(dualUnits("21.3", "Msi"), { english: "21.3 Msi", si: "146.858 GPa" });
  assert.deepEqual(dualUnits(1, "MPa"), { english: "145.038 psi", si: "1 MPa" });
  assert.deepEqual(dualUnits(1, "GPa"), { english: "0.145038 Msi", si: "1 GPa" });
  assert.equal(dualUnits("1", "lb/in³").si, "27,679.9 kg/m³");
  assert.equal(dualUnits("1", "lb/ft³").si, "16.0185 kg/m³");
  assert.equal(dualUnits("1", "in").si, "25.4 mm");
  assert.equal(dualUnits("-0.5", "10⁻⁶/°F").si, "-0.9 10⁻⁶/K");
  assert.equal(dualUnits("-250", "ksi").si, "-1,723.69 MPa");
  assert.deepEqual(dualUnits(".27", "—"), { english: "0.27", si: "0.27" });
});

test("ranges are converted at both ends, missing values stay missing, and questionable magnitudes are not corrected", () => {
  assert.deepEqual(dualUnits("45–49", "%"), { english: "45–49 %", si: "45–49 %" });
  assert.equal(dualUnits("1–2", "in").si, "25.4–50.8 mm");
  assert.equal(dualUnits("-2–-1", "in").si, "-50.8–-25.4 mm");
  assert.deepEqual(dualUnits("TBD", "in"), { english: "Not provided", si: "Not provided" });
  assert.equal(dualUnits("-87300", "ksi").si, "-601,912 MPa");
  assert.equal(dualUnits("1", "unknown").si, "Conversion unavailable");
  for (const p of [...materials.flatMap(m => m.properties), ...references.flatMap(r => r.properties)]) {
    const values = dualUnits(p.value, p.unit);
    assert.notEqual(values.english, "Conversion unavailable", `${p.label}: ${p.value} ${p.unit}`);
    assert.notEqual(values.si, "Conversion unavailable", `${p.label}: ${p.value} ${p.unit}`);
  }
});
