import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { curatedMaterials, materialDatasets } from "../lib/curated-materials";
import { provenanceOf, sourceProvenance } from "../lib/source-provenance";
import qualificationReferences from "../lib/qualification-references.json";

// How a source was checked (fingerprints, review notes, rights evidence) is a review record. It stays in the repository, in
// lib/source-provenance.ts, and never in the code a page loads (ADR-0018 amendment 2).
const root = resolve(".");
// The review records, the card-to-function map, and the course-appendix audit and transcription (ADR-0042) stay off the pages.
const INTERNAL = ["lib/source-provenance.ts", "lib/source-provenance.json", "lib/physics-code-map.ts", "lib/material-analysis.ts", "lib/materials.ts"];

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap(name => { const path = join(dir, name); return statSync(path).isDirectory() ? walk(path) : [path]; });
}

function resolveImport(from: string, spec: string): string | null {
  const base = spec.startsWith("@/") ? join(root, spec.slice(2)) : spec.startsWith(".") ? resolve(dirname(from), spec) : null;
  if (!base) return null; // a package
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, `${base}.json`, join(base, "index.ts"), join(base, "index.tsx")])
    if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  return null;
}

/** Every repository module a page can load: everything reachable by import from app/ and components/. */
function clientModules(): Set<string> {
  const seen = new Set<string>();
  const queue = [...walk(join(root, "app")), ...walk(join(root, "components"))].filter(f => /\.(tsx?|json)$/.test(f));
  while (queue.length) {
    const file = queue.pop()!;
    if (seen.has(file)) continue;
    seen.add(file);
    if (file.endsWith(".json")) continue;
    const text = readFileSync(file, "utf8");
    for (const match of text.matchAll(/(?:import|export)\s[^;]*?from\s*["']([^"']+)["']|import\s*\(\s*["']([^"']+)["']\s*\)|import\s+["']([^"']+)["']/g)) {
      const target = resolveImport(file, match[1] ?? match[2] ?? match[3]);
      if (target) queue.push(target);
    }
  }
  return new Set([...seen].map(f => relative(root, f).replace(/\\/g, "/")));
}

test("no page or component can reach the review records", () => {
  const modules = clientModules();
  assert.ok(modules.has("lib/curated-materials.ts") && modules.has("lib/textbook-source.ts"), "the walk reaches the library");
  for (const internal of INTERNAL) assert.ok(!modules.has(internal), `${internal} is reachable from a page`);
  for (const module of [...modules].filter(m => m.startsWith("lib/")))
    assert.doesNotMatch(readFileSync(module, "utf8"), /\brightsEvidence\b|\bsha256\s*:|"sha256"|\bverification\s*:/, `${module} carries a review record`);
});

test("every cited source keeps its review record in the repository", () => {
  for (const m of curatedMaterials.flatMap(materialDatasets)) {
    for (const ref of [m.source, ...(m.supportingReferences || [])]) {
      const record = provenanceOf(ref.id);
      assert.ok(record.verification.length > 20 && record.rightsEvidence.length > 20, ref.id);
      if (m.source.kind !== "book") assert.match(record.sha256 ?? "", /^[a-f0-9]{64}$/, ref.id);
      for (const key of ["sha256", "verification", "rightsEvidence"]) assert.ok(!(key in ref), `${ref.id} still carries ${key}`);
    }
  }
  for (const ref of Object.values(qualificationReferences)) assert.ok(sourceProvenance[ref.id], ref.id);
  // The review records name no person and tie no value to a private model.
  assert.doesNotMatch(JSON.stringify(sourceProvenance), /founder|team's|San Diego licen|Abaqus/i);
});
