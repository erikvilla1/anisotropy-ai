import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { exportMaterialLibrary, libraryExportPath, renderMaterialLibrary } from "../scripts/export-material-library";
import { curatedMaterials, materialDatasets } from "../lib/curated-materials";

const LF = "\n";
const CRLF = "\r" + LF;

test("the committed engine library file is exactly what the website library exports (ADR-0020)", () => {
  // Windows checkouts may carry CRLF; the comparison is about content, not line endings.
  const committed = readFileSync(libraryExportPath, "utf8").split(CRLF).join(LF);
  assert.equal(committed, renderMaterialLibrary(), "run: npm run export:library");
});

test("every library dataset is exported once, with its values as recorded and a page for each", () => {
  const { datasets } = exportMaterialLibrary();
  assert.equal(datasets.length, curatedMaterials.flatMap(materialDatasets).length);
  assert.equal(new Set(datasets.map(d => d.datasetId)).size, datasets.length);
  for (const material of curatedMaterials) {
    const own = datasets.filter(d => d.materialId === material.id);
    assert.equal(own[0].datasetId, material.datasetId);
    assert.ok(own[0].primary && own.slice(1).every(d => !d.primary));
  }
  for (const d of datasets) {
    assert.ok(d.source.title && d.source.url && d.source.rights && d.source.page > 0);
    assert.ok(d.properties.length);
    for (const p of d.properties) {
      assert.ok(Number.isFinite(p.value) && p.unit && p.sourcePage > 0 && p.basis, `${d.datasetId} ${p.key}`);
    }
    if (d.elasticInputs) {
      for (const key of Object.values(d.elasticInputs)) assert.ok(d.properties.some(p => p.key === key), `${d.datasetId} lacks ${key}`);
    }
  }
  const im7 = datasets.find(d => d.datasetId === "ncamp-im7-8552-2019-rtd-measured-v1")!;
  assert.equal(im7.properties.find(p => p.key === "E1t")!.value, 23.51);
  assert.equal(im7.properties.find(p => p.key === "E1t")!.unit, "Msi");
});
