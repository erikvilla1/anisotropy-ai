import { randomUUID } from "node:crypto";
import { mkdirSync, existsSync, writeFileSync, renameSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { materialEvidence, type MaterialFeed, type SourceStatus } from "../../lib/material-evidence";
import { MonitorStore } from "./store";
import { extractProperties, revisionMetadata } from "./properties";

export function buildCatalog(store: MonitorStore): MaterialFeed {
  const result: MaterialFeed = { schemaVersion: 1, generatedAt: new Date().toISOString(), sources: [], candidates: [], releases: [] };
  for (const state of store.list()) {
    const source = store.source(state.id);
    const snapshot = state.current ? store.snapshot(state.current.id)! : null;
    const pages = snapshot ? JSON.parse(snapshot.pages) : [];
    const meta = snapshot ? revisionMetadata(state.id, pages) : { revision: null, revisionDate: null, datePrecision: null, dateMeaning: "No source revision captured." };
    const status: SourceStatus = {
      id: state.id, name: state.name, kind: source.kind || "datasheet", sourceUrl: state.pageUrl,
      documentUrl: snapshot?.url || null, fingerprint: snapshot?.raw_hash || null, ...meta,
      lastChecked: state.last_attempt, lastSuccess: state.last_success, nextCheck: state.next_check,
      outcome: state.lastCheck ? String(state.lastCheck.outcome) : "not-checked", failed: !!state.error,
      review: snapshot ? (state.review?.decision as "accepted" | "rejected" || "pending") : "not-captured",
      propertyExtraction: snapshot ? "not-configured" : "not-captured",
    };
    result.sources.push(status);
    if (snapshot && !source.kind) {
      try {
        for (const candidate of extractProperties(state.id, pages)) {
          result.candidates.push({ ...candidate, sourceId: state.id, fingerprint: snapshot.raw_hash, status: "unreviewed" });
          status.propertyExtraction = "ready-for-review";
        }
      } catch { status.propertyExtraction = "review-required"; }
    }
  }
  const rows = store.db.prepare("SELECT payload FROM reference_releases ORDER BY approved_at,id").all();
  const latest = new Map<string, MaterialFeed["releases"][number]>();
  for (const row of rows) { const release = JSON.parse(String(row.payload)); latest.set(release.materialId, release); }
  result.releases = [...latest.values()];
  return result;
}

export function publishReference(store: MonitorStore, materialId: string, fingerprint: string, reviewer: string, note: string) {
  const identity = materialEvidence[materialId];
  if (!identity || identity.identity !== "identified") throw new Error("An exact material identity must be verified before publishing reference properties");
  if (typeof reviewer !== "string" || !reviewer.trim() || reviewer.length > 120 || typeof note !== "string" || !note.trim() || note.length > 3000) throw new Error("Reviewer and verification findings are required");
  // Keep selection, current-source checks, and append-only publication in one transaction.
  store.db.exec("BEGIN IMMEDIATE");
  try {
    const catalog = buildCatalog(store);
    const candidate = catalog.candidates.find(c => c.materialId === materialId && c.fingerprint === fingerprint);
    if (!candidate) throw new Error("No current, validated candidate matches this material and source fingerprint");
    const status = catalog.sources.find(s => s.id === candidate.sourceId)!;
    if (status.failed || status.review !== "accepted" || status.nextCheck < new Date().toISOString()) throw new Error("Source must pass a recent check and be accepted before publishing reference values");
    if (!candidate.properties.length || candidate.properties.some(p => !Number.isFinite(p.value) || p.value <= 0 || !p.method || !p.conditions || !p.evidence || !p.direction || !Number.isInteger(p.sourcePage) || p.sourcePage < 1)) throw new Error("Incomplete property evidence");
    const release: MaterialFeed["releases"][number] = { materialId, sourceId: candidate.sourceId, fingerprint,
      releaseId: randomUUID(), approvedAt: new Date().toISOString(), sourceRevision: status.revision, sourceRevisionDate: status.revisionDate,
      documentUrl: status.documentUrl!, properties: candidate.properties, use: "reference-only" };
    store.db.prepare("INSERT INTO reference_releases(id,material_id,source_id,snapshot_id,fingerprint,approved_at,reviewer,note,payload) VALUES(?,?,?,?,?,?,?,?,?)")
      .run(release.releaseId, materialId, release.sourceId, store.state(release.sourceId).snapshot_id, fingerprint, release.approvedAt, reviewer.trim(), note.trim(), JSON.stringify(release));
    store.db.exec("COMMIT");
    return release;
  } catch (error) { store.db.exec("ROLLBACK"); throw error; }
}

// Publish only allowlisted reference metadata and structured values. No reviewer names, notes,
// original PDFs, database paths, private source text, or API tokens enter the public site.
export function writeCatalog(store: MonitorStore, root = process.cwd()) {
  const payload = JSON.stringify(buildCatalog(store));
  const destinations = [resolve(root, "public/materials/catalog-status.json")];
  if (existsSync(resolve(root, "out"))) destinations.push(resolve(root, "out/materials/catalog-status.json"));
  for (const path of destinations) {
    mkdirSync(dirname(path), { recursive: true });
    const temporary = `${path}.${randomUUID()}.tmp`;
    writeFileSync(temporary, payload, { encoding: "utf8", mode: 0o600 });
    renameSync(temporary, path);
  }
}
