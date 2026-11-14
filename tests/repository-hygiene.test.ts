// The repository's own front matter stays true: what git ignores, what the README lists, and who owns the code (the 2026-11-12
// audit's findings repository-14 and documents-8; ADR-0096).
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";

function git(args: string[]): string | null {
  try {
    return execFileSync("git", args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return null;
  }
}
const inRepository = git(["rev-parse", "--is-inside-work-tree"])?.trim() === "true";
const noGit = inRepository ? false : "git or the repository's .git is not available here";

test("agent links and other tools' folders are ignored whether they are folders, junctions or symlinks", { skip: noGit }, () => {
  // `--no-index` judges the path by the rules alone. A path without a trailing slash is how git sees a symlink, so a rule written
  // `/.claude/skills/` (a directory only) would not match it.
  for (const path of [".claude/skills", ".claude/agents", ".agents", ".codex", ".DS_Store", "docs/.DS_Store"]) {
    assert.notEqual(git(["check-ignore", "--no-index", "-q", path]), null, `${path} is not ignored by .gitignore`);
  }
});

test("the README's project structure names every top-level folder the repository tracks", { skip: noGit }, () => {
  const folders = new Set(git(["ls-files"])!.split("\n").filter((f) => f.includes("/")).map((f) => f.split("/")[0]).filter((f) => !f.startsWith(".")));
  const readme = readFileSync("README.md", "utf8");
  const tree = readme.slice(readme.indexOf("## Project structure"), readme.indexOf("## Pages"));
  for (const folder of folders) assert.match(tree, new RegExp(`^${folder}/ `, "m"), `README.md's project structure does not list ${folder}/`);
});

test("the repository says who owns it: all rights reserved, and third-party values under their owners' terms", () => {
  const pkg = JSON.parse(readFileSync("package.json", "utf8")) as { license?: string };
  assert.equal(pkg.license, "UNLICENSED");
  assert.match(readFileSync("LICENSE", "utf8"), /^Copyright \(c\) \d{4} Anisotropy\. All rights reserved\./);
  const notice = readFileSync("NOTICE", "utf8");
  for (const kind of ["Public domain", "Open publisher", "Licensed reference"]) assert.match(notice, new RegExp(`^- ${kind}:`, "m"));
});

test("NOTICE names every partner's mark the site serves, since LICENSE claims all else for Anisotropy", () => {
  // LICENSE says the media are Anisotropy's "unless NOTICE names another owner"; a partner's mark is someone else's (ADR-0081).
  const notice = readFileSync("NOTICE", "utf8");
  const marks = readdirSync("public/assets/partners").filter((name) => !name.startsWith("."));
  assert.ok(marks.length > 0, "public/assets/partners holds no marks; update this test if they moved");
  for (const mark of marks) assert.ok(notice.includes(mark), `NOTICE does not name public/assets/partners/${mark}`);
});
