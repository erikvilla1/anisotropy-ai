// The Access sign-in page (ADR-0056 amendment 3) keeps the rules of Cloudflare's Access custom pages, and the committed page is
// the template with the mark inlined, so what is pasted into Cloudflare is what the repository reviews.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { ACCESS_DIR, MARK_PLACEHOLDER, buildAccessPage } from "../scripts/build-access-page";

const source = readFileSync(`${ACCESS_DIR}login-page.src.html`, "utf8");
const page = readFileSync(`${ACCESS_DIR}login-page.html`, "utf8");

test("the committed page is the template with the mark inlined (run npm run build:access-page after an edit)", () => {
  assert.equal(page, buildAccessPage(source, readFileSync(`${ACCESS_DIR}mark.webp`)));
  assert.ok(!page.includes(MARK_PLACEHOLDER));
});

test("the page has exactly one authbox, outside any Liquid condition or loop", () => {
  const opens = page.match(/<cf-access-authbox\b/g) ?? [];
  assert.equal(opens.length, 1);
  const before = page.slice(0, page.indexOf("<cf-access-authbox"));
  const depth = (tag: string, end: string) =>
    (before.match(new RegExp(`{%-?\\s*${tag}\\b`, "g")) ?? []).length - (before.match(new RegExp(`{%-?\\s*${end}\\b`, "g")) ?? []).length;
  for (const [tag, end] of [["if", "endif"], ["unless", "endunless"], ["for", "endfor"], ["case", "endcase"]]) {
    assert.equal(depth(tag, end), 0, `the authbox sits inside a {% ${tag} %}`);
  }
});

test("the page shows Access's message and carries no script, event handler, form or Liquid tag Cloudflare refuses", () => {
  assert.match(page, /{{\s*message\.text\s*}}/);
  assert.doesNotMatch(page, /<script\b/i);
  assert.doesNotMatch(page, /\son[a-z]+\s*=/i);
  assert.doesNotMatch(page, /<form\b/i);
  assert.doesNotMatch(page, /{%-?\s*(include|render|layout|echo|raw)\b/);
  assert.doesNotMatch(page, /\|\s*raw\b/);
  for (const url of page.match(/(?:href|src)="([^"]+)"/g) ?? []) {
    assert.match(url, /="(https:|data:image\/)/, `${url} is neither HTTPS nor an inline image`);
  }
});
