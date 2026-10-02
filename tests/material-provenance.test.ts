import { test } from "node:test";
import assert from "node:assert/strict";
import { materials } from "../lib/materials";
import { materialEvidence, standards, requireEngineeringProperties } from "../lib/material-evidence";
import { sources } from "../services/material-monitor/sources";
import { MonitorStore } from "../services/material-monitor/store";
import { buildCatalog, publishReference } from "../services/material-monitor/catalog";
import { extractProperties, revisionMetadata } from "../services/material-monitor/properties";
import { extractStandardMetadata, type Document } from "../services/material-monitor/documents";

// Deliberately synthetic numbers. These fixtures exercise identity/column boundaries,
// not a redistributed manufacturer property dataset.
const rows = [
  ["Compressive Strength", "ASTM D 1621"], ["Compressive Modulus", "ASTM D1621-B-73"],
  ["Tensile Strength", "ASTM D 1623"], ["Tensile Modulus", "ASTM D 1623"],
  ["Shear Strength", "ASTM C 273"], ["Shear Modulus", "ASTM C 273"],
];
const table = "Property Test Procedure Unit H45 H60 H80 H100 H130 H160 H200 H250 " +
  rows.map(([label, method]) => `${label} ${method} MPa Nominal 11 12 13 14 15 16 17 18 Minimum 1 2 3 4 5 6 7 8`).join(" ") +
  " Shear Strain All values measured at +23°C Properties measured perpendicular to the plane Datasheet Diab Divinycell H rev 26 SI May 2026";
const pages = [{ page: 1, text: table }];
const source = sources[0];
const doc = (text = table): Document => ({ url: "https://diab-media.azureedge.net/fixture.pdf", bytes: Buffer.from(text), pages: [{ page: 1, text }] });

test("every existing material has explicit traceability and no implicit engineering eligibility", () => {
  assert.equal(materials.length, 22);
  assert.deepEqual(Object.keys(materialEvidence).sort(), materials.map(m => m.id).sort());
  for (const material of materials) {
    const e = materialEvidence[material.id];
    assert.ok(e.issue);
    assert.ok(e.methodIds.every(id => standards[id]));
    assert.ok(e.sourceIds.every(id => sources.some(s => s.id === id)));
    assert.throws(() => requireEngineeringProperties(material.id), /No qualified/);
  }
  for (const id of ["carbon-weave-vartm", "glass-weave-wet", "carbon-ud-nominal"]) {
    assert.equal(materialEvidence[id].identity, "identity-needed");
    assert.deepEqual(materialEvidence[id].sourceIds, []);
  }
  assert.throws(() => requireEngineeringProperties("unknown"), /Unknown/);
});

test("revision dates retain publisher precision and never infer copyright or upload dates", () => {
  assert.equal(revisionMetadata(source.id, pages).revisionDate, "2026-05");
  assert.equal(revisionMetadata(source.id, pages).datePrecision, "month");
  assert.equal(revisionMetadata("hexcel-hrh10-us", [{ page: 1, text: "Copyright 2017. Uploaded 2026." }]).revisionDate, null);
  assert.equal(revisionMetadata("toray-ex1515", [{ page: 1, text: "TORAY_EX1515_PDS_v5.1_2020-01-28" }]).revisionDate, "2020-01-28");
  assert.equal(revisionMetadata("baltek-sbc", [{ page: 1, text: "DATA SHEET 07.2025" }]).revisionDate, "2025-07");
});

test("standard metadata selects active edition, ignores scripts and fails closed on ambiguity", () => {
  const astm = sources.find(s => s.id === "astm-d3039")!;
  const html = '<body><script>D3039_D3039M-99 Active</script>D3039_D3039M-17 Historical D3039_D3039M-17R25 Active <span class="last-updated">Last Updated: Dec 02, 2025</span></body>';
  const result = extractStandardMetadata(html, astm);
  assert.deepEqual(result, { edition: "D3039_D3039M-17R25", catalogUpdated: "Dec 02, 2025" });
  assert.equal(revisionMetadata(astm.id, [{ page: 1, text: JSON.stringify(result) }]).revisionDate, "2025-12-02");
  assert.throws(() => extractStandardMetadata("<body>Edition removed</body>", astm), /active/);
  assert.throws(() => extractStandardMetadata(html.replace("Historical", "Active"), astm), /active/);
  assert.ok(astm.pageUrl.includes("/standards/"));
});

test("grade extraction preserves columns, units, test edition and nominal/minimum basis", () => {
  const records = extractProperties(source.id, pages);
  assert.equal(records.length, 2);
  assert.equal(records[0].properties.length, 12);
  assert.equal(records[0].properties[0].value, 11);
  assert.equal(records[1].properties[0].value, 18);
  assert.equal(records[0].properties[1].basis, "minimum");
  assert.equal(records[0].properties[2].method, "ASTM D1621-B-73");
  assert.equal(records[0].properties[0].unit, "MPa");
  for (const changed of [table.replace("H45 H60", "H60 H45"), table.replace("11 12 13", "11 12"), table.replace("Minimum 1", "Minimum 99"), table.replace("+23°C", "+80°C"), table.replace("MPa", "psi")]) {
    assert.throws(() => extractProperties(source.id, [{ page: 1, text: changed }]));
  }
  assert.deepEqual(extractProperties("hexcel-criii", pages), []);
});

test("reference publication is explicit, immutable, and preserves its revision after an update", t => {
  const db = new MonitorStore(":memory:", [source]); t.after(() => db.close());
  db.recordSuccess(source, doc());
  let catalog = buildCatalog(db);
  const fingerprint = catalog.sources[0].fingerprint!;
  assert.equal(catalog.releases.length, 0);
  assert.equal(catalog.sources[0].propertyExtraction, "ready-for-review");
  assert.throws(() => publishReference(db, "divinycell-h45", fingerprint, "Reviewer", "Checked"), /accepted/);
  db.review(db.state(source.id).snapshot_id!, "accepted", "Private reviewer", "Private findings");
  assert.equal(buildCatalog(db).releases.length, 0);
  assert.throws(() => publishReference(db, "carbon-weave-vartm", fingerprint, "Reviewer", "Checked"), /identity/);
  const release = publishReference(db, "divinycell-h45", fingerprint, "Private reviewer", "Private findings");
  assert.equal(release.use, "reference-only");
  assert.equal(release.sourceRevisionDate, "2026-05");
  assert.equal(release.documentUrl, doc().url);
  assert.throws(() => publishReference(db, "divinycell-h45", fingerprint, "Reviewer", "Checked"), /UNIQUE/);
  assert.throws(() => db.db.exec("DELETE FROM reference_releases"), /immutable/);
  db.recordSuccess(source, doc(table.replace("11 12 13", "21 22 23").replace("rev 26", "rev 27")));
  catalog = buildCatalog(db);
  assert.equal(catalog.sources[0].review, "pending");
  assert.equal(catalog.releases[0].fingerprint, fingerprint);
  assert.equal(catalog.releases[0].properties[0].value, 11);
  assert.equal(catalog.candidates[0].properties[0].value, 21);
  assert.throws(() => publishReference(db, "divinycell-h45", fingerprint, "Reviewer", "Old"), /current/);
  const publicJson = JSON.stringify(catalog);
  assert.doesNotMatch(publicJson, /Private reviewer|Private findings|pages":|bytes":/);
  assert.throws(() => requireEngineeringProperties("divinycell-h45"), /No qualified/);
});

test("failed or overdue checks prevent publishing; changed tables expose an extraction failure", t => {
  const db = new MonitorStore(":memory:", [source]); t.after(() => db.close());
  db.recordSuccess(source, doc());
  db.review(db.state(source.id).snapshot_id!, "accepted", "Reviewer", "Checked");
  const fingerprint = buildCatalog(db).sources[0].fingerprint!;
  db.recordFailure(source, "Publisher unavailable");
  assert.throws(() => publishReference(db, "divinycell-h45", fingerprint, "Reviewer", "Checked"), /recent/);
  db.recordSuccess(source, doc(), new Date("2020-01-01T00:00:00Z"));
  assert.throws(() => publishReference(db, "divinycell-h45", fingerprint, "Reviewer", "Checked"), /recent/);
  db.recordSuccess(source, doc(table.replace("H45 H60", "H60 H45")));
  const catalog = buildCatalog(db);
  assert.equal(catalog.candidates.length, 0);
  assert.equal(catalog.sources[0].propertyExtraction, "review-required");
});

test("honeycomb extraction requires reported method, direction headers and consistent basis", () => {
  const text = "Room Temperature 0.500 inch thickness tested per AMS-STD-401 Compressive Plate Shear Bare Stabilized L Direction W Direction Strength psi Strength psi Modulus ksi Strength psi Modulus ksi Strength psi Modulus ksi HRH-10 - 1/8 - 1.8 110 90 120 100 8 90 70 4 50 40 2 HRH-10 - 1/8 - 3.0";
  const result = extractProperties("hexcel-hrh10-us", [{ page: 4, text }])[0];
  assert.equal(result.properties[7].direction, "L");
  assert.equal(result.properties[10].direction, "W");
  assert.equal(result.properties[7].unit, "ksi");
  assert.equal(result.properties[0].sourcePage, 4);
  for (const changed of [text.replace("AMS-STD-401", "OTHER"), text.replace("L Direction W Direction", "W Direction L Direction"), text.replace("110 90", "110 190")]) assert.throws(() => extractProperties("hexcel-hrh10-us", [{ page: 4, text: changed }]));
});

test("M55J extraction keeps its own process, flags inconsistent unit pairs and rejects changed conditions", () => {
  const rows = [["Tensile Strength 0°",3039,1896,"MPa",275,"ksi"],["Tensile Modulus 0°",3039,354,"GPa",50,"Msi"],
    ["Compressive Strength 0°",6641,731,"MPa",106,"ksi"],["Compressive Modulus 0°",6641,310,"GPa",45,"Msi"],
    ["Flexural Strength 0°",7264,1089,"MPa",158,"ksi"],["Flexural Modulus 0°",7264,317,"GPa",46,"Msi"],["Interlaminar Shear Strength",2344,62,"MPa",9,"ksi"]];
  const text = "LAMINATE DATA - TORAY M55J (78 Msi/538 GPa) PAN GRAPHITE/EX-1515 " + rows.map(([label,method,si,unit,us,usUnit]) => `${label} RTD ASTM D ${method} ${si} ${unit} ${us} ${usUnit}`).join(" ") + " Standard 121°C (250°F) Autoclave cure 85 psi, normalized to 60% fiber volume.";
  const result = extractProperties("toray-ex1515", [{ page:3, text }])[0];
  assert.equal(result.properties.length, 7);
  assert.equal(result.properties.filter(p => p.review).length, 1);
  assert.equal(result.properties[1].value, 354);
  assert.match(result.properties[1].review!, /disagree/);
  assert.match(result.properties[0].conditions, /autoclave/);
  assert.throws(() => extractProperties("toray-ex1515", [{page:3,text:text.replace("85 psi", "90 psi")}]));
});
