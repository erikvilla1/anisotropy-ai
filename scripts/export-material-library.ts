/**
 * Export the website's cited material library to the JSON file the engine reads (ADR-0020).
 *
 *   npx tsx scripts/export-material-library.ts
 *
 * One dataset per entry, in library order, with every recorded value, its printed unit, page
 * and reference link. The engine converts to SI when it loads a dataset; this file keeps the
 * values exactly as the library records them. `tests/material-library-export.test.ts` fails
 * when the committed file no longer matches the library, so the two cannot drift apart.
 */
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { curatedMaterials, materialDatasets, type CitedMaterial } from "../lib/curated-materials";

export const libraryExportPath = resolve(__dirname, "../engine/src/anisotropy_engine/data/material-library.json");

function dataset(material: CitedMaterial, primary: boolean) {
  const { id, title, publisher, revision, date, url, sha256, page, rights } = material.source;
  return {
    materialId: material.id, name: material.name, family: material.family, architecture: material.architecture,
    datasetId: material.datasetId, dataset: material.dataset, primary,
    recordRevision: material.recordRevision ?? null, reviewedOn: material.reviewedOn ?? null,
    conditions: material.conditions, application: material.application,
    elasticInputs: material.elasticInputs ?? null,
    source: { id, title, publisher, revision, date, url, sha256, page, rights },
    properties: material.properties.map(p => ({
      key: p.key, label: p.label, value: p.value,
      ...(p.valueEnd === undefined ? {} : { valueEnd: p.valueEnd }),
      ...(p.valueQualifier === undefined ? {} : { valueQualifier: p.valueQualifier }),
      unit: p.unit, symbol: p.symbol ?? p.key, basis: p.basis, direction: p.direction, method: p.method,
      sourcePage: p.sourcePage, ...(p.printedPage === undefined ? {} : { printedPage: p.printedPage }),
      ...(p.sourceValue === undefined ? {} : { sourceValue: p.sourceValue }),
      ...(p.sourceUnit === undefined ? {} : { sourceUnit: p.sourceUnit }),
    })),
  };
}

export function exportMaterialLibrary() {
  const datasets = curatedMaterials.flatMap(material => materialDatasets(material).map((d, i) => dataset(d, i === 0)));
  return { schemaVersion: 1, generatedFrom: "lib/curated-materials.ts via scripts/export-material-library.ts", datasets };
}

export function renderMaterialLibrary() {
  return JSON.stringify(exportMaterialLibrary(), null, 2) + "\n";
}

if (require.main === module) {
  writeFileSync(libraryExportPath, renderMaterialLibrary(), "utf8");
  const { datasets } = exportMaterialLibrary();
  console.log(`wrote ${datasets.length} datasets for ${new Set(datasets.map(d => d.materialId)).size} materials to ${libraryExportPath}`);
}
