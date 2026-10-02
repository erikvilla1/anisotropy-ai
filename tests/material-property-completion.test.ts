import { test } from "node:test";
import assert from "node:assert/strict";
import { curatedMaterials, materialDatasets, exportCitedMaterial, currentMaterial } from "../lib/curated-materials";
import { textbookMaterials } from "../lib/textbook-materials";
import { dualUnits, propertyDisplayValue, propertyGroup } from "../lib/property-units";
import published from "../lib/published-material-references.json";
import type { MaterialFeed } from "../lib/material-evidence";

test("A.6 transcription preserves directions, blank cells and positive orthotropic compliance", () => {
  // Independently transcribed from the visually checked printed p. 380, in
  // E3, G23, G13, ν23, ν13, F3t, F3c, F23, F13 order.
  const expected: Record<string, (number | undefined)[]> = {
    "as4-3501": [10.3, 3.7, 7, .54, .27, 57, 228, undefined, undefined],
    "m10e-3783": [11.6, 3.6, 2.6, .20, .15, 27, 237, 44, 41],
    "agp370-3501-6s": [13.8, 4.1, 5.1, .37, .50, 60, 813, 65, 75],
  };
  const keys = ["E3", "G23", "G13", "nu23", "nu13", "F3t", "F3c", "F23", "F13"];
  for (const [id, cells] of Object.entries(expected)) {
    const m = textbookMaterials.find(m => m.id === id)!;
    const p = Object.fromEntries(m.properties.map(p => [p.key, p]));
    keys.forEach((key, i) => {
      assert.equal(p[key]?.value, cells[i], `${id}: ${key}`);
      if (cells[i] !== undefined) assert.equal(p[key].printedPage, 380);
    });
    const a = 1 / p.E1.value, b = 1 / p.E2.value, c = 1 / p.E3.value;
    const d = -p.nu12.value / p.E1.value, e = -p.nu13.value / p.E1.value, f = -p.nu23.value / p.E2.value;
    assert.ok(a > 0 && a * b - d * d > 0);
    assert.ok(a * b * c + 2 * d * e * f - a * f * f - b * e * e - c * d * d > 0);
    assert.ok(p.G12.value > 0 && p.G13.value > 0 && p.G23.value > 0);
  }
  const p = (id: string, key: string) => textbookMaterials.find(m => m.id === id)!.properties.find(p => p.key === key);
  assert.equal(p("7781-5245c", "Vf")!.value, 45);
  assert.equal(p("im6g-3501-6", "alpha1")!.value, -.9);
  assert.equal(p("im6g-3501-6", "beta1")!.value, 0);
  assert.equal(p("im6g-3501-6", "beta2"), undefined);
  assert.equal(p("as4-3501", "beta3")!.value, .2);
  assert.equal(p("agp370-3501-6s", "beta3")!.value, .27);
  assert.equal(p("m10e-3783", "alpha3"), undefined);
});

test("reported ranges, lower bounds and absolute temperatures survive display and export", () => {
  assert.deepEqual(dualUnits(32, "°F"), { english: "32 °F", si: "0 °C" });
  assert.deepEqual(dualUnits(100, "°C"), { english: "212 °F", si: "100 °C" });
  assert.equal(dualUnits("32–212", "°F").si, "0–100 °C");
  assert.equal(dualUnits("1.81–1.86", "g/cm³").si, "1,810–1,860 kg/m³");
  assert.equal(dualUnits(".0091–.0101", "in").si, "0.23114–0.25654 mm");
  assert.deepEqual(dualUnits(.2, "strain/unit c"), { english: "0.2 strain/unit c", si: "0.2 strain/unit c" });
  const glass = curatedMaterials.find(m => m.id === "7781-e765")!;
  const range = exportCitedMaterial(glass).properties.find(p => p.key === "density-WT")!;
  assert.equal(range.value, 1.81);
  assert.equal(range.valueEnd, 1.86);
  assert.equal(range.valueType, "range");
  assert.equal(exportCitedMaterial(glass).schemaVersion, 2);
  assert.equal(range.sourceUnit, "g/cm³");
  assert.equal(range.displayUnits.si, "1,810–1,860 kg/m³");
  assert.match(range.referenceUrl, /#page=29$/);
  const agp = curatedMaterials.find(m => m.id === "agp370")!;
  const lowerBound = exportCitedMaterial(agp).properties.find(p => p.key === "gamma31")!;
  assert.equal(lowerBound.valueQualifier, ">");
  assert.equal(lowerBound.valueType, "lower-bound");
  assert.equal(lowerBound.displayUnits.si, "> 7 %");
  assert.equal(propertyGroup("Ultimate out-of-plane tensile strain"), "Strength");
  assert.equal(propertyGroup("Glass transition temperature · dry"), "Thermal & moisture");
});

test("all expanded datasets retain distinct identities, defined units and exact references", () => {
  const records = curatedMaterials.flatMap(materialDatasets);
  assert.equal(new Set(records.map(m => m.datasetId)).size, records.length);
  for (const m of records) for (const p of m.properties) {
    assert.doesNotMatch(JSON.stringify(dualUnits(propertyDisplayValue(p), p.unit)), /unavailable|NaN|Not provided/);
    if (p.valueEnd !== undefined) assert.ok(p.valueEnd >= p.value);
  }
  const [book, nasa] = materialDatasets(curatedMaterials[0]);
  assert.equal(book.properties.find(p => p.key === "E1")!.value, 147);
  assert.equal(nasa.properties.find(p => p.key === "E1")!.value, 142);
  assert.ok(!book.properties.some(p => p.key === "tply"));
  assert.ok(!nasa.properties.some(p => p.key === "F1t"));
  const [legacy, modern] = materialDatasets(curatedMaterials.find(m => m.id === "7781-e765")!);
  assert.ok(legacy.properties.some(p => p.key === "nu12"));
  assert.ok(!modern.properties.some(p => p.key === "nu12"));
});

test("supplier supplements remain pinned to their reviewed fingerprint", () => {
  const base = curatedMaterials.find(m => m.id === "divinycell-h45")!;
  assert.equal(base.properties.find(p => p.key === "density")!.value, 48); // Not inferred from H45.
  const release = structuredClone(published.find(m => m.materialId === base.id)!) as MaterialFeed["releases"][number];
  release.approvedAt = "2026-10-03T12:00:00Z";
  release.releaseId = "new-supplier-release";
  release.fingerprint = "a".repeat(64);
  const feed: MaterialFeed = { schemaVersion: 1, generatedAt: release.approvedAt, sources: [], candidates: [], releases: [release] };
  const next = currentMaterial(base, feed);
  assert.equal(next.datasetId, release.releaseId);
  assert.ok(!next.properties.some(p => p.key === "density")); // Never attach old values to a new source.
});
