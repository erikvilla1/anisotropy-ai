import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { releaseDay, releaseProblems, releases, type Release } from "../lib/changelog";

// The site's changelog (ADR-0077 amendment 46): what the home page lists as published versions.

const example: Release = {
  version: "Engine 0.1.0",
  date: "2026-10-02",
  title: "The first engine",
  changes: [{ kind: "Added", text: "Laminate analysis." }, { kind: "Fixed", text: "A unit." }],
};

test("a list of releases that cannot be shown is noticed", () => {
  assert.deepEqual(releaseProblems([example]), []);
  assert.deepEqual(releaseProblems([{ ...example, version: "Engine 0.2.0", date: "2026-11-20" }, example]), []);
  // Newest first, each version once, a real day, a title, at least one change of a known kind with words in it.
  assert.ok(releaseProblems([example, { ...example, version: "Engine 0.2.0", date: "2026-11-20" }]).length > 0);
  assert.ok(releaseProblems([example, example]).length > 0);
  assert.ok(releaseProblems([{ ...example, date: "2 October 2026" }]).length > 0);
  assert.ok(releaseProblems([{ ...example, date: "2026-13-40" }]).length > 0);
  assert.ok(releaseProblems([{ ...example, title: " " }]).length > 0);
  assert.ok(releaseProblems([{ ...example, changes: [] }]).length > 0);
  assert.ok(releaseProblems([{ ...example, changes: [{ kind: "Removed" as "Fixed", text: "x" }] }]).length > 0);
  assert.ok(releaseProblems([{ ...example, changes: [{ kind: "Added", text: "" }] }]).length > 0);
  assert.equal(releaseDay("2026-10-02"), "October 2, 2026");
});

test("what the site lists is whole, and is a released version of CHANGELOG.md with the same day", () => {
  assert.deepEqual(releaseProblems(releases), []);
  const recorded = readFileSync(join(process.cwd(), "CHANGELOG.md"), "utf8");
  for (const release of releases) assert.ok(recorded.includes(`## [${release.version}] - ${release.date}`), `${release.version} of ${release.date} is not a released version in CHANGELOG.md`);
  // Nothing is published yet (the lead, 2026-11-14). The first release listed changes this line with it.
  assert.equal(releases.length, 0);
});
