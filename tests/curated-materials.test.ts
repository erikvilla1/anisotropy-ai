import { test } from "node:test";
import assert from "node:assert/strict";
import { materials } from "../lib/materials";
import { curatedMaterials, archivedMaterialReasons, currentMaterial, exportCitedMaterial, materialDatasets } from "../lib/curated-materials";
import { qualifiedCarbon, qualifiedCarbonIM7, qualifiedT650, qualifiedBT250, qualifiedGlass } from "../lib/qualification-materials";
import { dualUnits } from "../lib/property-units";
import published from "../lib/published-material-references.json";
import type { MaterialFeed } from "../lib/material-evidence";
import { retrieveDocument } from "../services/material-monitor/documents";
import { sources } from "../services/material-monitor/sources";
import { MonitorStore } from "../services/material-monitor/store";
import { buildCatalog } from "../services/material-monitor/catalog";

test("every original record is explicitly curated or archived; public values have complete citations", () => {
  const active = curatedMaterials.map(m => m.id);
  assert.equal(active.length, 18);
  assert.equal(Object.keys(archivedMaterialReasons).length, 13);
  assert.deepEqual([...active.filter(id => materials.some(m => m.id === id)), ...Object.keys(archivedMaterialReasons)].sort(), materials.map(m => m.id).sort());
  for (const m of curatedMaterials.flatMap(materialDatasets)) {
    assert.match(m.source.url, /^https:\/\//);
    assert.ok(m.source.title && m.source.publisher && m.source.accessed && m.application && m.conditions);
    assert.ok(m.source.kind === "book" || sources.some(s => s.id === m.source.id));
    assert.ok(m.properties.length);
    assert.equal(new Set(m.properties.map(p => p.key)).size, m.properties.length);
    for (const p of m.properties) {
      assert.ok(Number.isFinite(p.value));
      assert.ok(p.sourcePage > 0 && p.evidence && p.basis && p.method && p.conditions && p.direction);
      assert.doesNotMatch(JSON.stringify(dualUnits(p.value, p.unit)), /unavailable|Not provided|NaN/);
    }
    assert.doesNotMatch(JSON.stringify(exportCitedMaterial(m)), /Appendix F|SE143AB|source review required/);
  }
});

test("scientific definitions and source-specific measurements are not interchanged", () => {
  const ncamp = materialDatasets(qualifiedGlass)[1];
  const value = (key: string) => ncamp.properties.find(p => p.key === key)!;
  assert.equal(value("E1t").value, 3.700); // Measured RTD, not normalized 3.683 or cold 3.697.
  assert.equal(value("E1c").value, 3.868);
  assert.equal(value("F12-offset").value, 5.002);
  assert.equal(value("F12-5pct").value, 8.962);
  assert.equal(value("SBS").method, "ASTM D2344/D2344M-16");
  assert.ok(ncamp.properties.filter(p => /^(E[12][tc]|F|G12|SBS)/.test(p.key)).every(p => p.basis === "Measured mean"));
  assert.equal(ncamp.source.sha256, "1eefc09bc58939ef84806bcb00b60c2e282a9db628352b38de66c03930d52816");
  const as4 = materialDatasets(curatedMaterials.find(m => m.id === "as4-3501")!)[1];
  assert.equal(as4.properties.find(p => p.key === "E1")!.value, 142);
  assert.ok(as4.properties.every(p => p.basis === "Model input"));
  assert.equal(curatedMaterials.find(m => m.id === "m55j")!.properties.length, 7);
  assert.ok(!curatedMaterials.find(m => m.id === "m55j")!.properties.some(p => /Tensile Modulus/i.test(p.label)));
  assert.equal(dualUnits(-.36, "10⁻⁶/K").english, "-0.2 10⁻⁶/°F");
  assert.equal(dualUnits(25.4, "mm").english, "1 in");
});

test("qualification records supply coherent elastic inputs and keep the two glass programs separate", () => {
  for (const record of [qualifiedCarbon, qualifiedGlass]) {
    const inputs = Object.fromEntries(Object.entries(record.elasticInputs!).map(([name, key]) => [name, record.properties.find(p => p.key === key)!.value]));
    assert.ok(inputs.E1 > 0 && inputs.E2 > 0 && inputs.G12 > 0);
    // Reciprocity and positive in-plane elastic compliance; no borrowed missing constants.
    const nu21 = inputs.nu12 * inputs.E2 / inputs.E1;
    assert.ok(1 - inputs.nu12 * nu21 > 0);
    assert.equal(Object.keys(inputs).length, 4);
    assert.equal(record.reviewedOn, "2026-10-02");
    for (const ref of [record.source, ...record.supportingReferences!]) {
      assert.match(ref.sha256!, /^[a-f0-9]{64}$/);
      const adapter = sources.find(s => s.id === ref.id)!;
      assert.equal(adapter.pageUrl, ref.url);
      assert.equal(adapter.kind, "reference-document");
    }
    const out = exportCitedMaterial(record);
    assert.deepEqual(out.elasticInputs, record.elasticInputs);
    assert.equal(out.recordRevision, "2026-10-02.1");
    assert.equal(out.source.date, record.source.date); // Review date must not replace publication date.
    assert.ok(out.properties.every(p => p.referenceUrl.startsWith(record.source.url)));
  }
  const value = (m: typeof qualifiedGlass, key: string) => m.properties.find(p => p.key === key)!;
  assert.equal(value(qualifiedGlass, "nu12").value, .157);
  assert.equal(value(qualifiedGlass, "E1t").value, 3.73);
  assert.equal(value(qualifiedGlass, "F12").value, 19.05);
  assert.equal(value(qualifiedGlass, "F12").method, "ASTM D5379-93");
  assert.ok(!qualifiedGlass.properties.some(p => p.key === "SBS")); // Original report restricts it to QC.
  const modern = materialDatasets(qualifiedGlass)[1];
  assert.equal(value(modern, "E1t").value, 3.700);
  assert.ok(!modern.properties.some(p => p.key === "nu12"));
  assert.equal(modern.elasticInputs, undefined);
  assert.equal(value(qualifiedCarbon, "E1t").value, 19.09);
  assert.equal(value(qualifiedCarbon, "nu12").value, .302);
  assert.equal(value(qualifiedCarbon, "F1c-derived").basis, "Derived lamina mean");
  assert.equal(value(qualifiedCarbon, "F1c-derived").value, 215.29);
  assert.equal(value(qualifiedCarbon, "F12-offset").value, 8);
  assert.equal(value(qualifiedCarbon, "F12-5pct").value, 13.28);
  assert.match(value(qualifiedCarbon, "SBS").conditions, /^70°F/);
  assert.match(value(qualifiedCarbon, "E1t").conditions, /^75°F/);
  assert.equal(qualifiedCarbon.properties.length, 21);
  assert.equal(qualifiedGlass.properties.length, 19);
});

test("only newer reviewed releases of the same property definitions can replace bundled values", () => {
  const base = curatedMaterials.find(m => m.id === "divinycell-h45")!;
  const release = structuredClone(published.find(m => m.materialId === base.id)!) as MaterialFeed["releases"][number];
  release.approvedAt = "2026-10-02T12:00:00Z"; release.releaseId = "test-reviewed-release";
  release.fingerprint = "a".repeat(64); release.properties[0].value = .61;
  const feed: MaterialFeed = { schemaVersion: 1, generatedAt: release.approvedAt, sources: [], candidates: [], releases: [release] };
  assert.equal(currentMaterial(base, feed).properties[0].value, .61);
  assert.equal(currentMaterial(base, null).properties[0].value, .6);
  for (const mutate of [
    (r: typeof release) => { r.sourceId = "different-material"; },
    (r: typeof release) => { r.properties[0].conditions = "Hot/wet"; },
    (r: typeof release) => { r.properties[0].unit = "ksi"; },
    (r: typeof release) => { r.documentUrl = "https://unrelated.example/doc.pdf"; },
    (r: typeof release) => { r.properties[1] = r.properties[0]; },
  ]) {
    const bad = structuredClone(release); mutate(bad);
    assert.equal(currentMaterial(base, { ...feed, releases: [bad] }), base);
  }
  const exported = exportCitedMaterial(currentMaterial(base, feed));
  assert.equal(exported.datasetId, release.releaseId);
  assert.equal(exported.designAllowables, false);
  assert.equal(exported.source.sha256, release.fingerprint);
});

test("publication monitoring detects document replacement without extracting or publishing numerical values", async t => {
  const source = sources.find(s => s.id === "nasa-maddocks-as4")!;
  t.mock.method(globalThis, "fetch", async () => new Response("%PDF-1.7 original fixture"));
  const original = await retrieveDocument(source);
  const db = new MonitorStore(":memory:", [source]); t.after(() => db.close());
  db.recordSuccess(source, original);
  assert.equal(buildCatalog(db).candidates.length, 0);
  t.mock.restoreAll();
  t.mock.method(globalThis, "fetch", async () => new Response("%PDF-1.7 revised fixture"));
  assert.equal(db.recordSuccess(source, await retrieveDocument(source)), "changed");
  assert.equal(buildCatalog(db).releases.length, 0);
  t.mock.restoreAll();
  t.mock.method(globalThis, "fetch", async () => new Response("<html>Access challenge</html>"));
  await assert.rejects(retrieveDocument(source), /Expected a PDF/);
});

test("IM7 / 8552 record uses the measured RTD column of the 2019 report and keeps its sources separate from AS4", () => {
  const value = (key: string) => qualifiedCarbonIM7.properties.find(p => p.key === key)!;
  assert.equal(qualifiedCarbonIM7.id, "im7-8552");
  assert.equal(value("E1t").value, 23.51); // Measured, not normalized 22.99.
  assert.equal(value("E2t").value, 1.30);
  assert.equal(value("nu12").value, .316);
  assert.equal(value("G12").value, .68);
  assert.equal(value("F1t").value, 371.08);
  assert.equal(value("F1c-derived").value, 251.13);
  assert.equal(value("F1c-derived").basis, "Derived lamina mean");
  assert.equal(value("F12-5pct").value, 13.22);
  assert.equal(value("SBS").sourcePage, 37);
  assert.equal(value("tply").value, .0072);
  assert.equal(qualifiedCarbonIM7.properties.length, 21);
  assert.equal(qualifiedCarbonIM7.source.sha256, "640c215e6999e3429ed410722432174fb02e9157c76ae323380b9f314f211387");
  assert.equal(qualifiedCarbonIM7.source.date, "2019-04-16");
  assert.equal(qualifiedCarbonIM7.source.rights, "open-publisher");
  assert.match(qualifiedCarbonIM7.source.rightsEvidence, /general distribution to the public/);
  for (const ref of [qualifiedCarbonIM7.source, ...qualifiedCarbonIM7.supportingReferences!]) {
    const adapter = sources.find(s => s.id === ref.id)!;
    assert.equal(adapter.pageUrl, ref.url);
    assert.equal(adapter.kind, "reference-document");
  }
  assert.deepEqual(sources.find(s => s.id === "ncamp-im7-8552-data")!.materials.map(m => m.id), ["im7-8552"]);
  assert.ok(sources.find(s => s.id === "ncamp-as4-8552-data")!.materials.every(m => m.id === "as4-8552"));
  const inputs = Object.fromEntries(Object.entries(qualifiedCarbonIM7.elasticInputs!).map(([name, key]) => [name, value(key).value]));
  assert.ok(1 - inputs.nu12 * (inputs.nu12 * inputs.E2 / inputs.E1) > 0);
  assert.notEqual(qualifiedCarbon.datasetId, qualifiedCarbonIM7.datasetId);
  const out = exportCitedMaterial(qualifiedCarbonIM7);
  assert.ok(out.properties.every(p => p.referenceUrl.startsWith(qualifiedCarbonIM7.source.url)));
  assert.doesNotMatch(JSON.stringify(out), /22\.99|362\.69|248\.94/); // Normalized values are not in the record.
});

test("T650 / 5320-1 and IM7 / BT250E-6 records use the measured RTD column and have their own monitored reports", () => {
  const expected = {
    "t650-5320-1": { record: qualifiedT650, E1t: 20.077, E2t: 1.331, nu12: .326, G12: .718, F1t: 299.004, F1c: 237.875, F12: 13.501, SBS: 15.639, tply: .0055,
      sha: "3f65281e0bcfde5341cb0c7e06c1b96fe0f4306d1a0d7130f1dbe2863bfc63ed", date: "2017-01-27", normalized: /299\.093|237\.098|20\.082/ },
    "im7-bt250e-6": { record: qualifiedBT250, E1t: 22.603, E2t: 1.248, nu12: .309, G12: .629, F1t: 355.785, F1c: 213.784, F12: 10.084, SBS: 9.874, tply: .0058,
      sha: "304a088a4a497ed641e121b06c1a281d1c8cd440efd9782cde8c9d6db82e7683", date: "2017-10-25", normalized: /346\.642|205\.905|22\.015/ },
  };
  for (const [id, e] of Object.entries(expected)) {
    const m = e.record;
    const value = (key: string) => m.properties.find(p => p.key === key)!;
    assert.equal(m.id, id);
    assert.equal(value("E1t").value, e.E1t);
    assert.equal(value("E2t").value, e.E2t);
    assert.equal(value("nu12").value, e.nu12);
    assert.equal(value("G12").value, e.G12);
    assert.equal(value("F1t").value, e.F1t);
    assert.equal(value("F1c-derived").value, e.F1c);
    assert.equal(value("F1c-derived").basis, "Derived lamina mean");
    assert.equal(value("F12-5pct").value, e.F12);
    assert.equal(value("SBS").value, e.SBS);
    assert.equal(value("tply").value, e.tply);
    assert.equal(m.properties.length, 19);
    assert.equal(m.source.sha256, e.sha);
    assert.equal(m.source.date, e.date);
    assert.equal(m.source.rights, "open-publisher");
    assert.match(m.source.rightsEvidence, /general distribution to the public/);
    for (const ref of [m.source, ...m.supportingReferences!]) {
      const adapter = sources.find(s => s.id === ref.id)!;
      assert.equal(adapter.pageUrl, ref.url);
      assert.equal(adapter.kind, "reference-document");
      assert.deepEqual(adapter.materials.map(x => x.id), [id]);
      assert.match(ref.sha256!, /^[a-f0-9]{64}$/);
    }
    const inputs = Object.fromEntries(Object.entries(m.elasticInputs!).map(([name, key]) => [name, value(key).value]));
    assert.ok(1 - inputs.nu12 * (inputs.nu12 * inputs.E2 / inputs.E1) > 0);
    const out = exportCitedMaterial(m);
    assert.ok(out.properties.every(p => p.referenceUrl.startsWith(m.source.url)));
    assert.doesNotMatch(JSON.stringify(out), e.normalized);
  }
  assert.equal(new Set(curatedMaterials.map(m => m.datasetId)).size, curatedMaterials.length);
});
