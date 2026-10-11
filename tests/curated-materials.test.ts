import { test } from "node:test";
import assert from "node:assert/strict";
import { materials } from "../lib/materials";
import { curatedMaterials, archivedMaterialReasons, currentMaterial, exportCitedMaterial, materialDatasets } from "../lib/curated-materials";
import { qualifiedCarbon, qualifiedCarbonIM7, nasaCarbonIM7, qualifiedT650, qualifiedBT250, qualifiedTC380, qualifiedEP2190, qualifiedAS4PW, qualifiedT650PW, qualifiedTC250, handbookT650976, handbookEA9396, qualifiedGlass } from "../lib/qualification-materials";
import { dualUnits } from "../lib/property-units";
import published from "../lib/published-material-references.json";
import type { MaterialFeed } from "../lib/material-evidence";
import { retrieveDocument } from "../services/material-monitor/documents";
import { sources } from "../services/material-monitor/sources";
import { MonitorStore } from "../services/material-monitor/store";
import { buildCatalog } from "../services/material-monitor/catalog";

test("every original record is explicitly curated or archived; public values have complete citations", () => {
  const active = curatedMaterials.map(m => m.id);
  assert.equal(active.length, 25);
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

test("T1100GC / TC380 and IMS65 / EP2190 records use the measured room-temperature column and keep their test conditions distinct", () => {
  const expected = {
    "t1100gc-tc380": { record: qualifiedTC380, E1t: 22.97, E2t: 1.111, nu12: .3132, G12: .5740, F1t: 475.3, F1cKey: "F1c-derived", F1c: 236.2, F1cBasis: "Derived lamina mean", F12: 11.16, SBS: 14.40, tply: .0048, count: 20,
      sha: "e8297c644af8e437a482edb78717b83dee49ed3c52c91b2c963a0dfbb8bd446b", date: "2025-09-24", normalized: /472\.6|226\.7|22\.84/, environment: /70°F/ },
    "ims65-ep2190": { record: qualifiedEP2190, E1t: 22.04, E2t: 1.255, nu12: .3299, G12: .6053, F1t: 415.8, F1cKey: "F1c", F1c: 207.7, F1cBasis: "Measured mean", F12: 10.63, SBS: 12.64, tply: .0056, count: 20,
      sha: "99a3d37118965e0933878c06de2222a65264f3fc1171836555d11697217c5dfc", date: "2025-09-18", normalized: /430\.6|218\.1|22\.81/, environment: /75°F.*ambient/ },
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
    assert.equal(value(e.F1cKey).value, e.F1c);
    assert.equal(value(e.F1cKey).basis, e.F1cBasis);
    assert.equal(value("F12-5pct").value, e.F12);
    assert.equal(value("SBS").value, e.SBS);
    assert.equal(value("tply").value, e.tply);
    assert.equal(m.properties.length, e.count);
    assert.match(m.conditions, e.environment);
    assert.ok(m.properties.every(p => e.environment.test(p.conditions)));
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
  // EP2190 is measured directly in compression; TC380 is a cross-ply back-out. The keys say which.
  assert.ok(!qualifiedEP2190.properties.some(p => p.key === "F1c-derived"));
  assert.ok(!qualifiedTC380.properties.some(p => p.key === "F1c"));
  assert.equal(new Set(curatedMaterials.map(m => m.id)).size, curatedMaterials.length);
});

test("NASA 2023 IM7 / 8552 dataset sits beside the NCAMP record with printed averages, page offsets and its own monitored report", () => {
  const m = nasaCarbonIM7;
  const value = (key: string) => m.properties.find(p => p.key === key)!;
  assert.deepEqual(materialDatasets(qualifiedCarbonIM7).map(d => d.datasetId), [qualifiedCarbonIM7.datasetId, m.datasetId]);
  assert.ok(!curatedMaterials.includes(m)); // A second dataset of an existing material, not a 21st material.
  assert.equal(m.id, "im7-8552");
  assert.equal(value("E1t").value, 23.105148);
  assert.equal(value("E1t").sourceValue, 23105148);
  assert.equal(value("E1t").sourceUnit, "psi");
  assert.equal(value("E2t").value, 1.299337);
  assert.equal(value("nu12").value, .3235);
  assert.equal(value("G12").value, .650712);
  assert.equal(value("G23").value, .414695);
  assert.equal(value("G13").value, .763931);
  assert.equal(value("E3t").value, 1.089994);
  assert.equal(value("F1t").value, 392.337); // Printed average, not the last replicate 391,111 psi.
  assert.equal(value("F1c").value, 116.744);
  assert.equal(value("F1c").basis, "Measured mean");
  assert.match(value("F1c").conditions, /end-crushing/);
  assert.equal(value("F12-5pct").value, 14.492);
  assert.equal(value("F23").value, 7.41);
  assert.equal(value("tply").value, .18);
  assert.equal(value("tply").unit, "mm");
  assert.equal(value("SG").value, 1.61);
  assert.equal(m.properties.length, 24);
  assert.ok(!m.properties.some(p => p.key === "F1c-derived" || p.key === "SBS"));
  for (const p of m.properties) {
    assert.equal(p.printedPage, p.sourcePage - 6);
    assert.match(p.conditions, /^Room temperature, quasi-static/);
    assert.doesNotMatch(p.conditions, /70°F|75°F|dry as fabricated/);
  }
  assert.equal(m.source.sha256, "8720e1dce2830b9cae264627a637d74b1bca4d7a2cec078a29c52ae61e7e7eeb");
  assert.equal(m.source.date, "2023-02");
  assert.equal(m.source.rights, "open-publisher");
  assert.match(m.source.rightsEvidence, /Public Use Permitted/);
  assert.equal(m.supportingReferences, undefined);
  const adapter = sources.find(s => s.id === m.source.id)!;
  assert.equal(adapter.pageUrl, m.source.url);
  assert.equal(adapter.kind, "reference-document");
  assert.deepEqual(adapter.materials.map(x => x.id), ["im7-8552"]);
  assert.ok(adapter.maxDocumentBytes! >= 10_000_000);
  const inputs = Object.fromEntries(Object.entries(m.elasticInputs!).map(([name, key]) => [name, value(key).value]));
  assert.ok(1 - inputs.nu12 * (inputs.nu12 * inputs.E2 / inputs.E1) > 0);
  const out = exportCitedMaterial(m);
  assert.notEqual(out.datasetId, exportCitedMaterial(qualifiedCarbonIM7).datasetId);
  assert.ok(out.properties.every(p => p.referenceUrl.startsWith(m.source.url)));
  assert.ok(out.properties.some(p => p.referenceUrl.endsWith("#page=18")));
  assert.doesNotMatch(JSON.stringify(out), /391[,.]?111|23\.51|251\.13/); // Neither the mis-copied replicate nor NCAMP values.
});

test("NCAMP plain weave records use the measured RTD column, direct fabric compression and their own monitored reports", () => {
  const expected = {
    "as4-8552s-pw": { record: qualifiedAS4PW, E1t: 9.58, E2t: 9.66, nu12: .046, G12: .72, F1t: 111.52, F2t: 109.19, F1c: 122.37, F2c: 113.31, F12offset: 8.11, F12pct: null, SBS: 13.36, tply: .0078, count: 20,
      sha: "76fdace8746d4f5750373784888b72b6594738ed6b3e3d68009bd73c96efec7a", date: "2011-04-14", normalized: /109\.02|115\.13|9\.36/ },
    "t650-5320-1-pw": { record: qualifiedT650PW, E1t: 9.990, E2t: 9.931, nu12: .053, G12: .735, F1t: 124.900, F2t: 121.810, F1c: 106.167, F2c: 100.365, F12offset: 8.299, F12pct: 14.650, SBS: 11.035, tply: .0077, count: 19,
      sha: "edcf939a0b607c3e6c7053e7c0030d0364189b1ba3fa7d9b3839a7d8cb9438b0", date: "2015-10-13", normalized: /121\.838|102\.675|9\.738/ },
    "hts40-tc250": { record: qualifiedTC250, E1t: 8.66, E2t: 8.58, nu12: .040, G12: .52, F1t: 126.33, F2t: 121.76, F1c: 100.14, F2c: 89.96, F12offset: 5.72, F12pct: 9.87, SBS: 9.36, tply: .0085, count: 20,
      sha: "ccd1717a7c2b463223fbbef34638350c502aac62e7dd154c2acafd5ef068a8c1", date: "2016-09-26", normalized: /130\.41|101\.26|8\.94|1\.207/ },
  };
  for (const [id, e] of Object.entries(expected)) {
    const m = e.record;
    const value = (key: string) => m.properties.find(p => p.key === key)!;
    assert.equal(m.id, id);
    assert.match(m.architecture, /plain weave/);
    assert.equal(value("E1t").direction, "Warp");
    assert.equal(value("E2t").direction, "Fill");
    for (const [key, v] of Object.entries({ E1t: e.E1t, E2t: e.E2t, nu12: e.nu12, G12: e.G12, F1t: e.F1t, F2t: e.F2t, F1c: e.F1c, F2c: e.F2c, "F12-offset": e.F12offset, SBS: e.SBS, tply: e.tply })) assert.equal(value(key).value, v, key);
    if (e.F12pct === null) assert.ok(!m.properties.some(p => p.key === "F12-5pct")); else assert.equal(value("F12-5pct").value, e.F12pct);
    assert.equal(value("F1c").basis, "Measured mean");
    assert.ok(!m.properties.some(p => p.key === "F1c-derived"));
    assert.equal(m.properties.length, e.count);
    assert.ok(m.properties.every(p => /^70°F/.test(p.conditions)));
    assert.equal(m.source.sha256, e.sha);
    assert.equal(m.source.date, e.date);
    assert.equal(m.source.rights, "open-publisher");
    assert.match(m.source.rightsEvidence, /general distribution to the public/);
    for (const ref of [m.source, m.supportingReferences![0]]) {
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
    assert.ok(!out.properties.some(p => e.normalized.test(String(p.value)))); // Normalized columns and the unverified density are not values.
  }
  assert.ok(!qualifiedTC250.properties.some(p => p.key.startsWith("density"))); // Printed 1.207 g/cm³ is UNVERIFIED and not entered.
  assert.equal(new Set(curatedMaterials.map(m => m.id)).size, curatedMaterials.length);
});

test("MIL-HDBK-17-2F historical records are public domain, labelled canceled and keep the handbook data classes as basis", () => {
  for (const m of [handbookT650976, handbookEA9396]) {
    assert.match(m.dataset, /historical handbook data/);
    assert.match(m.conditions, /canceled 26 March 2013/);
    assert.match(m.conditions, /^72°F/);
    assert.equal(m.source.rights, "public-domain");
    assert.equal(m.source.id, "mil-hdbk-17-2f-volume-2");
    assert.equal(m.source.sha256, "a0368e3214a93ca859a50fc09d7cc3230cd4856d5be3e9ba1e9916f34758ff8b");
    assert.equal(m.source.date, "2002-06-17");
    assert.equal(m.supportingReferences![0].id, "mil-hdbk-17-2f-notice-1");
    assert.equal(m.supportingReferences![0].date, "2013-03-26");
    for (const p of m.properties) {
      assert.match(p.evidence, /handbook page \d-\d+ \(PDF page \d+\)/);
      assert.ok(["Mean", "Interim", "Screening", "B30", "B18", "Reported nominal", "Reported transition temperature"].includes(p.basis), p.basis);
    }
    const adapter = sources.find(s => s.id === m.source.id)!;
    assert.equal(adapter.pageUrl, m.source.url);
    assert.deepEqual(adapter.materials.map(x => x.id).sort(), ["7781-ea9396", "t650-35-976"]);
  }
  const t = (key: string) => handbookT650976.properties.find(p => p.key === key)!;
  assert.equal(t("F1t").value, 236); // Measured, not the normalized 231.
  assert.equal(t("F1t").basis, "B30");
  assert.equal(t("E1t").value, 22.5);
  assert.equal(t("E2t").basis, "Screening");
  assert.equal(t("G12").value, .745);
  assert.equal(t("F12").value, 14.9);
  assert.equal(t("F1t").sourcePage, 301);
  assert.equal(handbookT650976.elasticInputs, undefined); // No Poisson ratio printed.
  assert.ok(!handbookT650976.properties.some(p => /^(nu12|E1c|F1c)/.test(p.key)));
  assert.equal(handbookT650976.properties.length, 12);
  const g = (key: string) => handbookEA9396.properties.find(p => p.key === key)!;
  assert.equal(g("E1t").value, 3.62); // Measured, not the normalized 3.39.
  assert.equal(g("nu12").value, .115);
  assert.equal(g("nu12").basis, "Screening");
  assert.equal(g("F1c").value, 49.6);
  assert.equal(g("G12").value, .758);
  assert.equal(g("F12").sourcePage, 437);
  assert.match(handbookEA9396.conditions, /documentation presently required were not supplied/);
  assert.equal(handbookEA9396.properties.length, 15);
  assert.notEqual(handbookEA9396.id, qualifiedGlass.id); // Separate from the 7781 / E-765 prepreg record.
  const out = exportCitedMaterial(handbookT650976);
  assert.ok(!out.properties.some(p => [231, 202, 200].includes(p.value as number))); // Normalized and B-basis values stay in the handbook.
});
