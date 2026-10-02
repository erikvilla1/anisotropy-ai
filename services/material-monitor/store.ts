import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { randomUUID } from "node:crypto";
import { hash, textHash, changedPages, type Document, type PageText } from "./documents";
import type { Source } from "./sources";

type Snapshot = { id: number; source_id: string; captured_at: string; url: string; raw_hash: string; text_hash: string; pages: string; bytes: Uint8Array };
type State = { source_id: string; last_attempt: string | null; last_success: string | null; next_check: string; failures: number; error: string | null; snapshot_id: number | null };

export class MonitorStore {
  db: DatabaseSync;
  constructor(path: string, readonly sources: Source[]) {
    if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
    this.db = new DatabaseSync(path);
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA foreign_keys=ON;
      PRAGMA busy_timeout=5000;
      CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, captured_at TEXT NOT NULL,
        url TEXT NOT NULL, raw_hash TEXT NOT NULL, text_hash TEXT NOT NULL,
        pages TEXT NOT NULL, bytes BLOB NOT NULL, UNIQUE(source_id, raw_hash)
      ) STRICT;
      CREATE TABLE IF NOT EXISTS states (
        source_id TEXT PRIMARY KEY, last_attempt TEXT, last_success TEXT,
        next_check TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0, error TEXT,
        snapshot_id INTEGER REFERENCES snapshots(id)
      ) STRICT;
      CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, checked_at TEXT NOT NULL,
        outcome TEXT NOT NULL, message TEXT NOT NULL, snapshot_id INTEGER REFERENCES snapshots(id)
      ) STRICT;
      CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
        text_hash TEXT NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('accepted','rejected')),
        reviewer TEXT NOT NULL, note TEXT NOT NULL, reviewed_at TEXT NOT NULL,
        UNIQUE(source_id, snapshot_id)
      ) STRICT;
      CREATE TABLE IF NOT EXISTS leases (name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires TEXT NOT NULL) STRICT;
      CREATE TABLE IF NOT EXISTS reference_releases (
        id TEXT PRIMARY KEY, material_id TEXT NOT NULL, source_id TEXT NOT NULL,
        snapshot_id INTEGER NOT NULL REFERENCES snapshots(id), fingerprint TEXT NOT NULL,
        approved_at TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT NOT NULL, payload TEXT NOT NULL,
        UNIQUE(material_id, fingerprint)
      ) STRICT;
      CREATE TRIGGER IF NOT EXISTS releases_immutable_update BEFORE UPDATE ON reference_releases BEGIN SELECT RAISE(ABORT, 'Releases are immutable'); END;
      CREATE TRIGGER IF NOT EXISTS releases_immutable_delete BEFORE DELETE ON reference_releases BEGIN SELECT RAISE(ABORT, 'Releases are immutable'); END;
      CREATE TRIGGER IF NOT EXISTS snapshots_immutable_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT, 'Snapshots are immutable'); END;
      CREATE TRIGGER IF NOT EXISTS snapshots_immutable_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT, 'Snapshots are immutable'); END;
      CREATE TRIGGER IF NOT EXISTS reviews_immutable_update BEFORE UPDATE ON reviews BEGIN SELECT RAISE(ABORT, 'Reviews are immutable'); END;
      CREATE TRIGGER IF NOT EXISTS reviews_immutable_delete BEFORE DELETE ON reviews BEGIN SELECT RAISE(ABORT, 'Reviews are immutable'); END;
    `);
    for (const source of sources) this.db.prepare("INSERT OR IGNORE INTO states(source_id, next_check) VALUES (?, ?)").run(source.id, new Date(0).toISOString());
  }
  close() { this.db.close(); }
  state(id: string): State { return this.db.prepare("SELECT * FROM states WHERE source_id=?").get(id) as State; }
  snapshot(id: number): Snapshot | undefined { return this.db.prepare("SELECT * FROM snapshots WHERE id=?").get(id) as Snapshot | undefined; }
  source(id: string) {
    const source = this.sources.find(s => s.id === id);
    if (!source) throw new Error("Unknown source");
    return source;
  }
  acquire(now = new Date()): string | null {
    const owner = randomUUID();
    const result = this.db.prepare(`INSERT INTO leases(name, owner, expires) VALUES ('monitor', ?, ?)
      ON CONFLICT(name) DO UPDATE SET owner=excluded.owner, expires=excluded.expires WHERE leases.expires <= ?`)
      .run(owner, new Date(now.getTime() + 15 * 60_000).toISOString(), now.toISOString());
    return result.changes ? owner : null;
  }
  release(owner: string) { this.db.prepare("DELETE FROM leases WHERE name='monitor' AND owner=?").run(owner); }

  recordSuccess(source: Source, document: Document, now = new Date()) {
    const stamp = now.toISOString();
    const raw = hash(document.bytes);
    const semantic = textHash(document.pages);
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const state = this.state(source.id);
      const previous = state.snapshot_id ? this.snapshot(state.snapshot_id) : undefined;
      this.db.prepare("INSERT OR IGNORE INTO snapshots(source_id,captured_at,url,raw_hash,text_hash,pages,bytes) VALUES(?,?,?,?,?,?,?)")
        .run(source.id, stamp, document.url, raw, semantic, JSON.stringify(document.pages), document.bytes);
      const snapshot = this.db.prepare("SELECT id FROM snapshots WHERE source_id=? AND raw_hash=?").get(source.id, raw)!;
      const outcome = !previous ? "baseline" : previous.raw_hash === raw ? "unchanged" : previous.text_hash === semantic ? "binary-only" : "changed";
      const message = { baseline: "First source captured; review required", unchanged: "Source bytes unchanged", "binary-only": "PDF bytes changed; extracted text is unchanged. Layout/graphics were not compared.", changed: "Extracted source text changed; engineering impact requires review" }[outcome];
      this.db.prepare("INSERT INTO checks(source_id,checked_at,outcome,message,snapshot_id) VALUES(?,?,?,?,?)").run(source.id, stamp, outcome, message, snapshot.id);
      this.db.prepare("UPDATE states SET last_attempt=?,last_success=?,next_check=?,failures=0,error=NULL,snapshot_id=? WHERE source_id=?")
        .run(stamp, stamp, new Date(now.getTime() + source.intervalHours * 3_600_000).toISOString(), snapshot.id, source.id);
      this.db.exec("COMMIT");
      return outcome;
    } catch (error) { this.db.exec("ROLLBACK"); throw error; }
  }
  recordFailure(source: Source, message: string, now = new Date()) {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const failures = this.state(source.id).failures + 1;
      const stamp = now.toISOString();
      const retryMs = Math.min(6 * 3_600_000, 15 * 60_000 * 2 ** Math.min(failures - 1, 5));
      this.db.prepare("UPDATE states SET last_attempt=?,next_check=?,failures=?,error=? WHERE source_id=?")
        .run(stamp, new Date(now.getTime() + retryMs).toISOString(), failures, message, source.id);
      this.db.prepare("INSERT INTO checks(source_id,checked_at,outcome,message) VALUES(?,?,'failed',?)").run(source.id, stamp, message);
      this.db.exec("COMMIT");
    } catch (error) { this.db.exec("ROLLBACK"); throw error; }
  }
  list(now = new Date()) {
    return this.sources.map(source => {
      const state = this.state(source.id);
      const snapshot = state.snapshot_id ? this.snapshot(state.snapshot_id) : undefined;
      const review = snapshot ? this.db.prepare("SELECT decision,reviewer,note,reviewed_at,snapshot_id FROM reviews WHERE source_id=? AND snapshot_id=?").get(source.id, snapshot.id) : undefined;
      return { id: source.id, name: source.name, publisher: source.publisher, materials: source.materials,
        pageUrl: source.pageUrl, kind: source.kind || "datasheet", intervalHours: source.intervalHours, ...state,
        overdue: now.toISOString() > state.next_check,
        review: review || null,
        current: snapshot ? { id: snapshot.id, url: snapshot.url, capturedAt: snapshot.captured_at, hash: snapshot.raw_hash, pages: (JSON.parse(snapshot.pages) as PageText[]).length } : null,
        lastCheck: this.db.prepare("SELECT outcome,message FROM checks WHERE source_id=? ORDER BY id DESC LIMIT 1").get(source.id) || null,
      };
    });
  }
  detail(id: string) {
    this.source(id);
    const state = this.state(id);
    const current = state.snapshot_id ? this.snapshot(state.snapshot_id) : undefined;
    // Compare against the most recently accepted source, or the preceding observation.
    const accepted = this.db.prepare("SELECT snapshot_id FROM reviews WHERE source_id=? AND decision='accepted' ORDER BY id DESC LIMIT 1").get(id);
    let baseline = accepted ? this.snapshot(Number(accepted.snapshot_id)) : undefined;
    if (!baseline && current) baseline = this.db.prepare("SELECT * FROM snapshots WHERE source_id=? AND id < ? ORDER BY id DESC LIMIT 1").get(id, current.id) as Snapshot | undefined;
    const before = baseline ? JSON.parse(baseline.pages) as PageText[] : [];
    const after = current ? JSON.parse(current.pages) as PageText[] : [];
    return { source: this.list().find(s => s.id === id), baselineId: baseline?.id || null,
      changes: changedPages(before, after), pages: after,
      history: this.db.prepare("SELECT id,captured_at,url,raw_hash FROM snapshots WHERE source_id=? ORDER BY id DESC LIMIT 50").all(id),
      reviews: this.db.prepare("SELECT * FROM reviews WHERE source_id=? ORDER BY id DESC LIMIT 50").all(id),
      checks: this.db.prepare("SELECT * FROM checks WHERE source_id=? ORDER BY id DESC LIMIT 30").all(id),
    };
  }
  review(snapshotId: number, decision: string, reviewer: string, note: string) {
    if (!["accepted", "rejected"].includes(decision) || !reviewer?.trim() || !note?.trim() || reviewer.length > 120 || note.length > 3000) throw new Error("Decision, reviewer, and review note are required");
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const snapshot = this.snapshot(snapshotId);
      if (!snapshot) throw new Error("Snapshot not found");
      const state = this.state(snapshot.source_id);
      if (state.snapshot_id !== snapshotId || state.error || state.next_check < new Date().toISOString()) throw new Error("Source is stale, changed, or failed its latest check. Run a successful check before reviewing.");
      this.db.prepare("INSERT INTO reviews(source_id,snapshot_id,text_hash,decision,reviewer,note,reviewed_at) VALUES(?,?,?,?,?,?,?)")
        .run(snapshot.source_id, snapshot.id, snapshot.text_hash, decision, reviewer.trim(), note.trim(), new Date().toISOString());
      this.db.exec("COMMIT");
    } catch (error) { this.db.exec("ROLLBACK"); throw error; }
  }
}
