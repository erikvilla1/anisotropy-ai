import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { curatedMaterials, exportCitedMaterial, materialDatasets } from "../lib/curated-materials";
import { physicsTopics } from "../lib/physics";
import { sourceRightsClasses, sourceRightsPolicy } from "../lib/source-rights";
import { textbookSource } from "../lib/textbook-source";
import { citedSources } from "../lib/cited-sources";
import { bannedIn } from "../lib/studio-copy";

// What the materials library and the physics cards say to a customer (docs/copy-style-guide.md, ADR-0091): no tool or vendor,
// no decision number, no engine function, no team language, no review notes, and printed pages only (ADR-0018 amendment 2).
const INTERNAL: [string, RegExp][] = [
  ["decision number", /\bADR-\d/],
  ["engine", /\bengine\b/i],
  ["function name", /\b[a-z][a-z0-9]*_[a-z][a-z0-9_]*\b/],
  ["team language", /\b(?:co)?founder\b|\bteam\b/i],
  ["unchecked marker", /UNVERIFIED/],
  ["course material", /homework|SE143|Appendix F/i],
  ["fingerprint", /sha256|fingerprint/i],
  ["PDF page", /PDF p(?:age|\.)|supplied PDF/i],
  ["review diary", /could not be confirmed|not confirmed on \d|visual inspection|research copy/i],
];

function problems(where: string, text: string | undefined): string[] {
  if (!text) return [];
  return [...bannedIn(text), ...INTERNAL.filter(([, pattern]) => pattern.test(text)).map(([label]) => label)].map(label => `${where}: ${label} in "${text}"`);
}

test("the physics cards name no engine function, decision number or tool, and spell fibre and Tsai-Hill as the guide does", () => {
  const found: string[] = [];
  for (const topic of physicsTopics) {
    for (const [field, text] of Object.entries({ title: topic.title, subtitle: topic.subtitle, assumptions: topic.assumptions, source: topic.source }))
      found.push(...problems(`${topic.id}.${field}`, text));
    for (const m of topic.methods) {
      for (const [field, text] of Object.entries({ name: m.name, detail: m.detail, units: m.units, location: m.reference?.location }))
        found.push(...problems(`${m.name}.${field}`, text));
      for (const text of [m.name, m.detail, m.units ?? ""]) {
        if (/\bfiber/i.test(text)) found.push(`${m.name}: "fiber" in "${text}"`);
        if (/Tsai–(?:Hill|Wu)/.test(text)) found.push(`${m.name}: en dash in Tsai-Hill/Tsai-Wu`);
      }
    }
  }
  assert.deepEqual(found, []);
});

test("material records and their downloads carry customer facts only", () => {
  const found: string[] = [];
  for (const m of curatedMaterials.flatMap(materialDatasets)) {
    const where = m.datasetId;
    for (const text of [m.name, m.family, m.architecture, m.dataset, m.application, m.conditions, ...(m.recordDetails ?? []),
      m.source.title, m.source.publisher, m.source.revision, ...(m.supportingReferences ?? []).flatMap(r => [r.title, r.role, r.revision])])
      found.push(...problems(where, text));
    for (const p of m.properties) for (const text of [p.label, p.direction, p.method, p.conditions, p.evidence, p.basis, p.symbol])
      found.push(...problems(`${where}/${p.key}`, text));
    const download = JSON.stringify(exportCitedMaterial(m));
    found.push(...problems(`${where} download`, download.replace(/"(?:datasetId|referenceUrl|url)":"[^"]*"/g, "")));
    for (const key of ["verification", "rightsEvidence", "sha256", "recordRevision", "accessed"]) if (download.includes(`"${key}"`)) found.push(`${where} download: ${key}`);
    if (/Abaqus/i.test(download)) found.push(`${where} download: Abaqus`);
  }
  assert.deepEqual(found, []);
});

test("the rights classes and the references list speak to the customer", () => {
  const found: string[] = [];
  for (const rights of sourceRightsClasses) for (const text of [sourceRightsPolicy[rights].label, sourceRightsPolicy[rights].summary, sourceRightsPolicy[rights].note])
    found.push(...problems(rights, text));
  found.push(...problems("textbook", textbookSource.rightsNote));
  for (const group of citedSources()) for (const s of group.sources) found.push(...problems(s.url, `${s.title} ${s.detail}`));
  assert.deepEqual(found, []);
  assert.doesNotMatch(sourceRightsPolicy["licensed-reference"].summary, /we hold a copy/i);
});

// The library's own pages (audit shell-8, the shell group's hand-off): a link that opens a new tab says so to a screen reader
// and is the only kind with the up-right arrow; a same-tab link has none.
const LINK_FILES = ["app/library/page.tsx", "components/cited-material-properties.tsx", "components/physics-browser.tsx",
  "components/property-table.tsx", "components/source-viewer.tsx"];

test("a library link that opens a new tab says so, and only such a link has the up-right arrow", () => {
  const found: string[] = [];
  for (const file of LINK_FILES) {
    const source = readFileSync(file, "utf8");
    for (let at = source.indexOf('target="_blank"'); at >= 0; at = source.indexOf('target="_blank"', at + 1)) {
      const element = source.slice(source.lastIndexOf("<a", at), source.indexOf("</a>", at));
      if (!element.includes("(opens in a new tab)")) found.push(`${file}: new-tab link without "(opens in a new tab)": ${element.slice(0, 90)}`);
    }
    for (let at = source.indexOf("<Link"); at >= 0; at = source.indexOf("<Link", at + 1)) {
      const element = source.slice(at, source.indexOf("</Link>", at));
      if (/ArrowUpRight|↗/.test(element)) found.push(`${file}: same-tab link with the up-right arrow: ${element.slice(0, 90)}`);
    }
  }
  assert.deepEqual(found, []);
});

test("the library and the test-data page have their own title and description", () => {
  const library = readFileSync("app/library/layout.tsx", "utf8");
  assert.match(library, /title: "Materials library"/);
  assert.match(library, /description: "[^"]+"/);
  const data = readFileSync("app/data/page.tsx", "utf8");
  assert.match(data, /title: "Test data"/);
  assert.match(data, /description: "[^"]+"/);
  assert.match(data, /robots: \{ index: false, follow: false \}/);
  for (const text of [library, data].flatMap(t => [...t.matchAll(/(?:title|description): "([^"]+)"/g)].map(m => m[1])))
    assert.deepEqual(problems("metadata", text), []);
});
