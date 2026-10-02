import { test, type TestContext } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { allowedUrl, discoverDocument, changedPages, download, extractPdf, type Document } from "../services/material-monitor/documents";
import { sources } from "../services/material-monitor/sources";
import { MonitorStore } from "../services/material-monitor/store";
import { runChecks } from "../services/material-monitor/worker";

const source = sources[0];
function document(text = "H45 compression 0.6 MPa", bytes = text): Document {
  return { url: "https://diab-media.azureedge.net/example/diab-divinycell-h-rev26-si.pdf", bytes: Buffer.from(bytes), pages: [{ page: 1, text }] };
}
function store(t: TestContext) {
  const result = new MonitorStore(":memory:", [source]);
  t.after(() => result.close());
  return result;
}

test("source discovery follows a revised filename, deduplicates links, and fails closed on ambiguity", () => {
  const url = document().url;
  assert.equal(discoverDocument(`<nav>Changed navigation</nav><a href="${url}">data</a><a href="${url}">again</a>`, source), url);
  assert.throws(() => discoverDocument("<h1>Consent or error page</h1>", source), /found 0/);
  assert.throws(() => discoverDocument(`<a href="${url}">one</a><a href="${url.replace("rev26", "rev27")}">two</a>`, source), /found 2/);
  for (const url of ["http://diabgroup.com/x", "https://127.0.0.1/x", "https://diabgroup.com.evil.test/x", "https://user@diabgroup.com/x", "https://diabgroup.com:8443/x"]) assert.throws(() => allowedUrl(url, source));
});

test("download rejects redirects outside the registry and oversized response streams", async t => {
  t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 302, headers: { location: "http://127.0.0.1/private" } }));
  await assert.rejects(download(source.pageUrl, source, 1000), /allowlist/);
  t.mock.restoreAll();
  t.mock.method(globalThis, "fetch", async () => new Response("more than five bytes"));
  await assert.rejects(download(source.pageUrl, source, 5), /size limit/);
});

test("baseline requires review; identical checks do not duplicate snapshots or approvals", async t => {
  const db = store(t);
  await runChecks(db, true, async () => document());
  const initial = db.list()[0];
  assert.equal(initial.review, null);
  assert.equal(initial.lastCheck?.outcome, "baseline");
  db.review(initial.current!.id, "accepted", "Test reviewer", "Synthetic fixture reviewed");
  await runChecks(db, true, async () => document());
  assert.equal(db.list()[0].review?.decision, "accepted");
  assert.equal(db.detail(source.id).history.length, 1);
  assert.equal(db.list()[0].lastCheck?.outcome, "unchanged");
  assert.throws(() => db.review(initial.current!.id, "accepted", "Test reviewer", "Duplicate"), /UNIQUE/);
});

test("changed values create a pending revision; prior evidence remains immutable", async t => {
  const db = store(t);
  await runChecks(db, true, async () => document());
  const first = db.list()[0].current!.id;
  db.review(first, "accepted", "Test reviewer", "Original accepted");
  await runChecks(db, true, async () => document("H45 compression 0.7 MPa"));
  assert.equal(db.list()[0].review, null);
  assert.equal(db.list()[0].lastCheck?.outcome, "changed");
  assert.equal(db.detail(source.id).changes[0].before, "H45 compression 0.6 MPa");
  assert.equal(db.detail(source.id).changes[0].after, "H45 compression 0.7 MPa");
  assert.throws(() => db.review(first, "accepted", "Test reviewer", "Outdated screen"), /stale/);
  assert.throws(() => db.db.prepare("UPDATE snapshots SET url='x' WHERE id=?").run(first), /immutable/);
  assert.throws(() => db.db.exec("DELETE FROM reviews"), /immutable/);
});

test("binary-only changes still require review because graphics can change", async t => {
  const db = store(t);
  await runChecks(db, true, async () => document());
  db.review(db.list()[0].current!.id, "accepted", "Test reviewer", "Original accepted");
  await runChecks(db, true, async () => document("H45 compression 0.6 MPa", "different graphic bytes"));
  assert.equal(db.list()[0].lastCheck?.outcome, "binary-only");
  assert.equal(db.list()[0].review, null);
  assert.equal(db.detail(source.id).changes.length, 0);
});

test("failed checks preserve the last good snapshot and schedule a retry, never report unchanged", async t => {
  const db = store(t);
  await runChecks(db, true, async () => document());
  const before = db.list()[0];
  const results = await runChecks(db, true, async () => { throw new Error("Publisher unavailable"); });
  const after = db.list()[0];
  assert.equal(results[0].outcome, "failed");
  assert.equal(after.last_success, before.last_success);
  assert.equal(after.current!.id, before.current!.id);
  assert.equal(after.error, "Publisher unavailable");
  assert.equal(after.failures, 1);
  assert.ok(Date.parse(after.next_check) > Date.now());
  assert.throws(() => db.review(after.current!.id, "accepted", "Test reviewer", "Check failed"), /failed/);
});

test("scheduled checks respect due time and simultaneous workers cannot overlap", async t => {
  const db = store(t);
  await runChecks(db, true, async () => document());
  const results = await runChecks(db, false, async () => { throw new Error("Should not fetch before due"); });
  assert.deepEqual(results, []);
  const owner = db.acquire()!;
  await assert.rejects(runChecks(db, true, async () => document()), /Another monitor/);
  db.release("incorrect-owner");
  assert.equal(db.acquire(), null);
  db.release(owner);
  assert.ok(db.acquire());
});

test("review requires an explicit identity and note; rejection is retained", async t => {
  const db = store(t);
  await runChecks(db, true, async () => document());
  const id = db.list()[0].current!.id;
  assert.throws(() => db.review(id, "accepted", "", "note"), /required/);
  assert.throws(() => db.review(id, "approved-property", "Reviewer", "note"), /required/);
  db.review(id, "rejected", "Test reviewer", "Grade not sufficiently identified");
  await runChecks(db, true, async () => document());
  assert.equal(db.list()[0].review?.decision, "rejected");
});

test("page comparisons ignore whitespace but retain changed values and deleted pages", () => {
  assert.deepEqual(changedPages([{ page: 1, text: "H45  0.6\nMPa" }], [{ page: 1, text: "H45 0.6 MPa" }]), []);
  assert.equal(changedPages([{ page: 1, text: "H45 0.6 MPa" }], [{ page: 1, text: "H45 0.7 MPa" }]).length, 1);
  assert.equal(changedPages([{ page: 2, text: "Important conditions" }], [])[0].after, "");
});

test("captured source and review survive a service restart", async () => {
  const directory = mkdtempSync(join(tmpdir(), "anisotropy-monitor-test-"));
  const path = join(directory, "test.sqlite");
  let db = new MonitorStore(path, [source]);
  try {
    await runChecks(db, true, async () => document());
    const id = db.list()[0].current!.id;
    db.review(id, "accepted", "Test reviewer", "Persistence fixture");
    db.close();
    db = new MonitorStore(path, [source]);
    assert.equal(db.list()[0].current!.id, id);
    assert.equal(db.list()[0].review?.decision, "accepted");
    assert.equal(Buffer.from(db.snapshot(id)!.bytes).toString(), "H45 compression 0.6 MPa");
  } finally {
    db.close();
    // Remove only the explicitly created fixture files, never a recursive directory.
    for (const suffix of ["", "-wal", "-shm"]) rmSync(path + suffix, { force: true });
  }
});

test("real PDF extractor returns page evidence and rejects invalid bytes", async () => {
  const stream = "BT /F1 12 Tf 30 100 Td (DIVINYCELL H H45 H250 - synthetic fixture) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  for (let i = 0; i < objects.length; i++) { offsets.push(Buffer.byteLength(pdf)); pdf += `${i + 1} 0 obj\n${objects[i]}\nendobj\n`; }
  const xref = Buffer.byteLength(pdf);
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(o => String(o).padStart(10, "0") + " 00000 n ").join("\n")}\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  const pages = await extractPdf(Buffer.from(pdf));
  assert.equal(pages[0].page, 1);
  assert.match(pages[0].text, /H45 H250/);
  await assert.rejects(extractPdf(Buffer.from("<html>access denied</html>")), /extraction failed/);
});
