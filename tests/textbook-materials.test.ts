import { test } from "node:test";
import assert from "node:assert/strict";
import { textbookMaterials } from "../lib/textbook-materials";
import { exportCitedMaterial, referenceUrl } from "../lib/curated-materials";

test("textbook records preserve SI definitions, original cells and book rather than PDF links", () => {
  assert.equal(textbookMaterials.length, 7);
  assert.equal(textbookMaterials.reduce((n, m) => n + m.properties.length, 0), 149);
  for (const m of textbookMaterials) {
    const p = Object.fromEntries(m.properties.map(p => [p.key, p]));
    assert.equal(m.source.date, "2006");
    assert.equal(m.source.kind, "book");
    assert.equal(m.source.page, m.source.printedPage! + 20);
    assert.match(m.source.revision, /978-0-19-515097-1/);
    assert.equal(referenceUrl(m.source, m.source.page), m.source.url);
    assert.ok(1 - p.nu12.value ** 2 * p.E2.value / p.E1.value > 0);
    assert.ok(p.G12.value > 0 && p.Vf.value > 0 && p.Vf.value < 100);
    assert.equal(p.density.value, p.density.sourceValue! * 1000);
    assert.equal(p.density.sourceUnit, "g/cm³");
    assert.ok(Math.abs(p.epsilon1t.value - p.epsilon1t.sourceValue! * 100) < 1e-12);
    assert.ok(!p.tply && p.nu21);
    assert.match(p.nu21.basis, /rounded/);
    const packet = exportCitedMaterial(m);
    assert.equal(packet.designAllowables, false);
    assert.ok(packet.properties.every(p => p.referenceUrl === m.source.url && p.printedPage && p.sourceValue !== undefined));
    assert.deepEqual(packet.elasticInputs, { E1: "E1", E2: "E2", G12: "G12", nu12: "nu12" });
  }
  const im6 = textbookMaterials.find(m => m.id === "im6g-3501-6")!;
  assert.equal(im6.properties.find(p => p.key === "alpha1")!.value, -.9);
  assert.ok(!im6.properties.some(p => p.key === "beta2")); // Actual blank cell remains absent.
  const m10 = textbookMaterials.find(m => m.id === "m10e-3783")!;
  assert.ok(!m10.properties.some(p => p.key.startsWith("alpha") || p.key.startsWith("beta")));
  assert.equal(m10.properties.find(p => p.key === "nu12")!.value, .11);
  const agp = textbookMaterials.find(m => m.id === "agp370-3501-6s")!;
  assert.equal(agp.properties.find(p => p.key === "alpha1")!.value, 3.4); // A.5, not A.6 or school row.
});
