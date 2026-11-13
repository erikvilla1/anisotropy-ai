import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { exportMaterialLibrary, libraryExportPath, renderMaterialLibrary } from "../scripts/export-material-library";
import { chenX840PW, citedByPrintedPage, curatedMaterials, exportCitedMaterial, materialDatasets } from "../lib/curated-materials";
import { libraryOptions } from "../lib/material-library-options";
import { textbookPages, textbookSource } from "../lib/textbook-source";

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

test("a book is exported with its printed pages only, and the calculator cites the printed page (ADR-0018 amendment 2)", () => {
  const books = exportMaterialLibrary().datasets.filter(d => d.source.id === textbookSource.id);
  assert.ok(books.length > 0);
  const printed = new Set(textbookPages.map(p => p.printedPage));
  for (const d of books) {
    assert.ok(printed.has(d.source.page), `${d.datasetId}: source page ${d.source.page}`);
    for (const p of d.properties) assert.equal(p.sourcePage, p.printedPage, `${d.datasetId} ${p.key}`);
  }
  assert.match(libraryOptions.find(o => o.datasetId === "daniel-ishai-2006-as4-3501-v2")!.citation, /E₁ from p\. 377$/);
  assert.match(libraryOptions.find(o => o.datasetId === "chen-2015-x840-z60-pw-v1")!.citation, /E₁ from p\. 79$/);
});

test("a source whose link opens a search is cited by its printed page too; a link to the document keeps its PDF page (ADR-0018 amendment 2)", () => {
  // Every value of a printed-page source has a printed page, so the export never falls back to the PDF page.
  for (const m of curatedMaterials.flatMap(materialDatasets).filter(m => citedByPrintedPage(m.source)))
    for (const p of m.properties) assert.ok(p.printedPage, `${m.datasetId} ${p.key} has no printed page`);
  // The X840 / Z60 dissertation: printed page 79, never its PDF page 99, in the engine's file and in the customer download.
  const chen = exportMaterialLibrary().datasets.find(d => d.datasetId === chenX840PW.datasetId)!;
  assert.equal(chen.source.page, 79);
  assert.equal(chen.source.linkKind, "search");
  assert.deepEqual([...new Set(chen.properties.map(p => p.sourcePage))], [79]);
  const download = exportCitedMaterial(chenX840PW);
  assert.equal(download.source.printedPage, 79);
  assert.ok(!("page" in download.source));
  assert.ok(download.properties.every(p => !("sourcePage" in p) && p.printedPage === 79));
  assert.doesNotMatch(JSON.stringify(download), /"(?:page|sourcePage)":99\b|#page=99\b/);
  // The NASA report's link is its public PDF: the export keeps the PDF page, which the engine's anchor uses.
  const nasa = exportMaterialLibrary().datasets.find(d => d.datasetId === "nasa-tm-20230001560-im7-8552-rt-measured-v1")!;
  assert.equal(nasa.source.kind, null);
  assert.equal(nasa.source.linkKind, null);
  const e1 = nasa.properties.find(p => p.key === nasa.elasticInputs!.E1)!;
  assert.equal(e1.sourcePage, 18);
  assert.equal(e1.printedPage, 12);
});
