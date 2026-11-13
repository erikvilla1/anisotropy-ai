import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  cardRows, cardText, connectorCommand, differences, ExchangeError, headline, megabytes, notComparedWords, percent, provenance, readComparison, readExchange,
  readUpload, readUploadKey, sendProblem, type Comparison,
} from "../lib/abaqus-exchange";
import { StudioError } from "../lib/studio-api";
import { ABAQUS_CARD_ALLOWS, bannedIn, bannedInAbaqusCard, downloadName } from "../lib/studio-copy";

// what `fea/tools/abaqus_upload.py compare --json` writes for four bundles of the public D3039 check, pinned by fea/tests/test_abaqus_upload.py
const written = (name: string) => JSON.parse(readFileSync(`tests/fixtures/abaqus/${name}.json`, "utf8"));
const comparison = (name: string) => readComparison(written(name)) as Comparison;
const LIMITS = { max_bundle_bytes: 50 * 1024 * 1024, max_uploads: 100 };
const upload = (name: string | null, more: Record<string, unknown> = {}) => ({
  id: "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11", actor: "studio", user_email: null, token_id: null, created_at: "2026-11-13T09:10:00+00:00", bundle_sha256: "ab".repeat(32),
  bundle_bytes: 253399, units: "mm-MPa", job: "Job-1", coupon: "IM7-UNT-L1", in_scope: true, may_train: false, job_id: "0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00",
  verdict: name ? written(name).verdict : null, compared_at: name ? "2026-11-13T09:10:04+00:00" : null, not_compared: null, facts: {}, comparison: name ? written(name) : null, ...more,
});

test("the card says the answer first: agrees, in how many places it differs, or that not every part was compared", () => {
  assert.deepEqual(headline(comparison("agrees")), { words: "Agrees with ours", tone: "pass" });
  assert.deepEqual(headline(comparison("differs")), { words: "Differs in 2 places", tone: "fail" });
  assert.deepEqual(headline(comparison("another-mesh")), { words: "Agrees with ours", tone: "pass" });
  assert.deepEqual(headline(comparison("incomplete")), { words: "Not every part could be compared", tone: "open" });
  assert.deepEqual(headline({ verdict: "refused", problems: ["x"] }), { words: "Not compared", tone: "open" });
  const one = comparison("differs");
  assert.equal(headline({ ...one, summary: { ...one.summary, places: 1 } }).words, "Differs in 1 place");
  assert.equal(provenance(comparison("agrees")), "Job-1, solved by Abaqus/Standard 2025: 1,488 of its elements beside ours.");
  assert.equal(provenance(comparison("another-mesh")), "Job-1, solved by Abaqus/Standard 2025: 132 of its elements beside ours, by position: the two meshes differ.");
});

test("its four lines are the model, the pull force, the gauge section and between gauge and tabs, each with the command's own numbers", () => {
  const agrees = cardRows(comparison("agrees"));
  assert.deepEqual(agrees.map((r) => [r.id, r.label, r.state, r.mark]), [["model", "The model", "same", "same"], ["force", "The pull force", "same", "within 1 %"],
    ["gauge", "The gauge section", "same", "within 1 %"], ["free", "Between gauge and tabs", "same", "within 3 %"]]);
  assert.equal(agrees[0].said, "The same as ours on all 20 items.");
  assert.match(agrees[1].said, /^Yours 16210 N, ours 16210 N \(ours [+-]0\.000 % from yours\)\.$/);
  assert.equal(agrees[2].said, "13,824 values; the largest difference is 0 % (σ₁, your element 673, ply 1).");
  assert.deepEqual([agrees[2].element, agrees[2].ply, agrees[3].element], [673, 1, 481]); // ours, for the viewer's Show

  const differs = cardRows(comparison("differs"));
  assert.deepEqual(differs.map((r) => [r.state, r.mark]), [["differs", "differs"], ["differs", "outside 1 %"], ["same", "within 1 %"], ["same", "within 3 %"]]);
  assert.equal(differs[0].said, "1 of 20 items differ.");
  assert.equal(differs[1].said, "Yours 17020 N, ours 16210 N (ours −4.762 % from yours)." /* the minus sign, as every number on the page */);

  const other = cardRows(comparison("another-mesh")); // on another mesh the free length is shown and not judged, and says so
  assert.equal(other[0].said, "The same as ours on all 16 items, compared without the mesh.");
  assert.deepEqual([other[3].state, other[3].mark], ["shown", "not judged"]);
  assert.equal(other[2].said, "3,456 values; the largest difference is 0.06182 % (middle principal stress, your element 170, ply 2).");
  assert.equal(other[3].said, "9,216 values; the largest difference is 12.49 % (γ₁₂, your element 247, ply 2). Shown, not judged: the two meshes differ.");
  assert.deepEqual([other[2].element, other[3].element], [675, 985]);

  const incomplete = cardRows(comparison("incomplete"));
  assert.deepEqual([incomplete[1].state, incomplete[1].mark, incomplete[1].said], ["open", "not compared", "Your file holds no reaction forces, so the pull force was not compared."]);
});

test("a difference is shown where it is: the item by name, yours beside ours, and the place", () => {
  assert.deepEqual(differences(comparison("agrees")), []);
  assert.deepEqual(differences(comparison("differs")), [
    { what: "Layup, bottom first", yours: "[30/0/-45/90/90/-45/0/30], 8 plies, from the length axis (Ori-1, local 1 along y)",
      ours: "[45/0/-45/90/90/-45/0/45], 8 plies, from the length axis (Ori-1, local 1 along y)", where: "the model" },
    { what: "The pull force", yours: "17020 N", ours: "16210 N", where: "the top grip" },
  ]);
  const base = comparison("agrees"); // a gauge value off: the command's summary says which quantity, where, and both values
  const off: Comparison = { ...base, verdict: "differs",
    criteria: base.criteria.map((c) => (c.criterion.startsWith("Gauge") ? { ...c, met: false } : c)),
    summary: { ...base.summary, places: 1, zones: { ...base.summary.zones, gauge: { ...base.summary.zones.gauge, quantity: "S11", worst: 0.0196, your_element: 700, layer: 2, yours: 1934.2, ours: 1896.3 } } } };
  assert.deepEqual(differences(off), [{ what: "σ₁, the gauge section", yours: "1934 MPa", ours: "1896 MPa", where: "your element 700, ply 2" }]);
  assert.equal(percent(-0.047619), "4.762 %");
  assert.equal(percent(3.2e-9), "3.2 × 10⁻⁷ %"); // a difference that is roundoff is never printed with an exponent in letters
  assert.equal(cardText("ours -0.007 % from yours, 1.5e+06 beside"), "ours −0.007 % from yours, 1.5 × 10⁶ beside");
});

test("an answer of another shape is not shown as a comparison", () => {
  assert.equal(readComparison({ verdict: "agrees" }), null);
  const old = written("agrees");
  delete old.summary; // a comparison written before the summary: the card asks for it to be compared again
  assert.equal(readComparison(old), null);
  assert.deepEqual(readComparison({ verdict: "refused", problems: ["your model has plies [1] and ours [1, 2]: not the same layup"] }),
    { verdict: "refused", problems: ["your model has plies [1] and ours [1, 2]: not the same layup"] });
  assert.equal(readUpload(upload("differs")).comparison?.verdict, "differs");
  assert.equal(readUpload(upload(null, { not_compared: "x" })).comparison, null);
  assert.throws(() => readUpload({ id: 3 }), StudioError);
  assert.deepEqual(readExchange({ uploads: true, connector_route: false, max_bundle_bytes: 1, max_uploads: 2, max_tokens: 3 }).connector_route, false);
  assert.throws(() => readExchange({ uploads: "yes" }), StudioError);
  assert.equal(readUploadKey({ id: "k", name: "lab", hint: "abcd", created_at: "2026-11-13T09:00:00+00:00", last_used_at: null, revoked_at: null }).hint, "abcd");
});

test("a file that is not taken says what happened and what to do next, in the card's words", () => {
  const refused = new ExchangeError("x", 422, "Not a bundle this version takes, so nothing was stored: no manifest.json in the zip; the entry ../escape.txt leaves the bundle");
  assert.deepEqual(sendProblem(refused, LIMITS), { words: "This is not a file the connector wrote, so nothing was stored. Send the file named <job>-anisotropy.zip.",
    reasons: ["no manifest.json in the zip", "the entry ../escape.txt leaves the bundle"] });
  assert.equal(sendProblem(new ExchangeError("x", 413, "A bundle is at most 52428800 bytes as sent"), LIMITS).words, "This file is larger than 50 MB, the most that can be sent.");
  assert.equal(sendProblem(new ExchangeError("x", 429, "You have 100 uploads stored; delete one to send another"), LIMITS).words,
    "You have 100 files stored, the most a person may keep. Remove one, then send again.");
  assert.match(sendProblem(new ExchangeError("x", 401, null), LIMITS).words, /^Your sign-in has ended\./);
  assert.match(sendProblem(new ExchangeError("x", 503, "The bundle could not be stored: disk"), LIMITS).words, /could not be read or stored just now\. Nothing was kept\. Try again\.$/);
  assert.equal(sendProblem(new ExchangeError("x", 404, "No upload 1 of yours"), LIMITS).words, "This file is no longer stored, or it belongs to someone else.");
  assert.equal(sendProblem(new ExchangeError("The service did not answer. Check your connection and try again.", undefined, null), LIMITS).words,
    "The service did not answer. Check your connection and try again.");
  // the API's reasons for no comparison (api/src/anisotropy_api/main.py, uploads.py), each in plain words
  const said = (reason: string) => notComparedWords(reason);
  assert.match(said("the bundle is out of the comparison's scope; the upload's facts say what our reader did not take"), /does not cover this model yet/);
  assert.match(said("the package of coupon job 7d0c is no longer there, so its files cannot stand beside the upload"), /Run the analysis again/);
  assert.match(said("the package of coupon job 7d0c has no 4-results/ours-every-output.csv with its JSON: that run is not one the comparison covers"), /this kind of coupon/);
  assert.match(said("the comparison did not run: the bundle's command did not answer in 240 s"), /Click Compare again\.$/);
  assert.match(said("coupon job 7d0c is running; an upload stands beside a run that is done"), /has not finished/);
  assert.equal(sendProblem(new ExchangeError("x", 409, "Not compared: the package of coupon job 7d0c is no longer there, so its files cannot stand beside the upload"), LIMITS).words,
    said("the package of coupon job 7d0c is no longer there"));
  for (const words of [said(""), said("anything else"), megabytes(LIMITS.max_bundle_bytes)]) assert.deepEqual(bannedIn(words), []);
});

test("the card may name Abaqus and the connector's file, and nothing else the page bans (ADR-0094 part 7)", () => {
  assert.deepEqual(ABAQUS_CARD_ALLOWS, ["Abaqus", ".py"]);
  assert.deepEqual(bannedInAbaqusCard("abaqus python anisotropy_connector.py Job-1.odb"), []);
  assert.deepEqual(bannedIn("abaqus python anisotropy_connector.py Job-1.odb"), ["Abaqus", ".py"]); // elsewhere on the page both stay banned
  assert.deepEqual(bannedInAbaqusCard("compared by CalculiX, see ADR-0094 and spec.toml"), ["CalculiX", ".toml", "ADR number"]);
  assert.equal(cardText("no reactions read: write them with abaqus_every_output.py (RF in the field output)"), "no reactions read: write them with abaqus_every_output.py (RF in the field output)");
  assert.equal(cardText("the CalculiX record says otherwise"), null);
  for (const name of ["agrees", "differs", "another-mesh", "incomplete"]) { // every word the card takes from the command for these four
    const c = comparison(name);
    const shown = [headline(c).words, provenance(c), ...cardRows(c).flatMap((r) => [r.label, r.said, r.mark]), ...differences(c).flatMap((d) => [d.what, d.yours, d.ours, d.where ?? ""]),
      ...c.model.items.flatMap((i) => [i.item, i.yours, i.ours])].join("\n");
    assert.deepEqual(bannedInAbaqusCard(shown), [], name);
  }
});

test("the command that sends from Abaqus names the key's file and never the key", () => {
  const command = connectorCommand({ apiAddress: "https://anisotropy.dev/api/", jobId: "0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00", coupon: "IM7-UNT-L1", units: "mm-MPa" });
  assert.equal(command, "abaqus python anisotropy_connector.py <your job>.odb --units mm-MPa --coupon IM7-UNT-L1 --send https://anisotropy.dev/api "
    + "--token-file anisotropy-key.txt --our-run 0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  assert.doesNotMatch(command, /anisotropy_upload_/);
  const odd = connectorCommand({ apiAddress: "http://localhost:8000", jobId: "j", coupon: "a coupon; rm -rf", units: "in-psi" });
  assert.equal(odd, "abaqus python anisotropy_connector.py <your job>.odb --units mm-MPa --send http://localhost:8000 --token-file anisotropy-key.txt --our-run j"); // a name that is not plain is left out; a deck of ours is in mm-MPa or m-Pa
  assert.equal(downloadName("abaqus_build", { standard: "ASTM D3039/D3039M-17", layup: "[45/0/-45/90]s" }), "D3039_[45-0--45-90]s_build.py");
});
