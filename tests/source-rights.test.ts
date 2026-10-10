import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { curatedMaterials, exportCitedMaterial, materialDatasets } from "../lib/curated-materials";
import { materials, materialSource } from "../lib/materials";
import { schoolCitation } from "../lib/material-analysis";
import { textbookSource } from "../lib/textbook-source";
import { handbookReferences, rightsPolicy, sourceRightsClasses, sourceRightsPolicy } from "../lib/source-rights";

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap(name => { const path = join(dir, name); return statSync(path).isDirectory() ? walk(path) : [path]; });
}

test("every public dataset names a rights class with evidence, and the class permits publication", () => {
  const datasets = curatedMaterials.flatMap(materialDatasets);
  assert.ok(datasets.length >= 15);
  for (const m of datasets) {
    for (const ref of [m.source, ...(m.supportingReferences || [])]) {
      assert.ok(sourceRightsClasses.includes(ref.rights), `${m.id}: ${ref.id} has no rights class`);
      assert.ok(ref.rightsEvidence.length > 20, `${m.id}: ${ref.id} needs rights evidence`);
      const policy = rightsPolicy(ref.rights);
      assert.equal(policy.publicRecord, true, `${m.id}: ${ref.rights} sources cannot appear in the public library`);
      // Nothing in the library links to a copy we host: every URL is the publisher's own.
      assert.match(ref.url, /^https:\/\//);
      assert.ok(!/anisotropy|localhost|\/assets\//i.test(ref.url));
      if (!policy.linkDocument) assert.equal(ref.kind === "book" || ref.rights === "licensed-reference", true);
    }
    const out = exportCitedMaterial(m);
    assert.equal(out.source.rights, m.source.rights);
    assert.ok(out.source.rightsEvidence);
  }
  assert.equal(textbookSource.rights, "licensed-reference");
  assert.equal(sourceRightsPolicy["user-supplied"].publicRecord, false);
  assert.equal(sourceRightsPolicy["public-domain"].copyDocument, true);
  for (const rights of sourceRightsClasses) if (rights !== "public-domain") assert.equal(sourceRightsPolicy[rights].copyDocument, false);
  assert.throws(() => rightsPolicy("unknown" as never), /Unknown source rights/);
});

test("course material is cited by page only: no public copy, no link, not tracked by git", () => {
  assert.equal(materialSource.public, false);
  assert.equal(existsSync("public/assets/documents/material-properties-2026-v2.pdf"), false, "The course appendix must not be a public asset");
  const citation = schoolCitation(materials[0]);
  assert.equal(citation.rights, "licensed-reference");
  assert.equal(citation.publicDocument, false);
  assert.ok(!("url" in citation));
  const ignore = readFileSync(".gitignore", "utf8");
  for (const rule of [".local/", "References/", "public/**/*.pdf", "public/assets/documents/material-properties-2026-v2*.pdf", "public/assets/documents/daniel-ishai-2006/"])
    assert.ok(ignore.includes(rule), `.gitignore must contain ${rule}`);
});

test("the website hosts no copied documents: no PDFs, scans or extracted text under public assets", () => {
  const files = walk("public");
  assert.deepEqual(files.filter(f => /\.(pdf|docx?|txt|json)$/i.test(f) && !/catalog-status\.json$/.test(f)), []);
  assert.deepEqual(files.filter(f => /daniel-ishai|cmh|mil-hdbk|se143|appendix|textbook/i.test(f)), []);
  assert.equal(existsSync("public/assets/documents/daniel-ishai-2006"), false);
});

test("handbooks the site names carry a rights class and are only linked at the publisher", () => {
  for (const ref of handbookReferences) {
    assert.ok(sourceRightsClasses.includes(ref.rights));
    assert.match(ref.url, /^https:\/\//);
    assert.ok(ref.rightsEvidence);
  }
  assert.equal(handbookReferences.find(r => r.id === "cmh-17-2g")!.rights, "licensed-reference");
  assert.equal(handbookReferences.find(r => r.id === "mil-hdbk-17-2f")!.rights, "public-domain");
});
