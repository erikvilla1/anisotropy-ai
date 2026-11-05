// The Access sign-in page (ADR-0056 amendment 3): access/login-page.src.html with the mark inlined as a data URL, written to
// access/login-page.html, the file pasted into Cloudflare's Access custom pages editor. The mark is inlined because the page is
// shown before sign-in, when every address on anisotropy.dev is behind Access and an <img> pointing there would not load.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const ACCESS_DIR = fileURLToPath(new URL("../access/", import.meta.url));
export const MARK_PLACEHOLDER = "__ANISOTROPY_MARK__";

export function buildAccessPage(source: string, mark: Buffer): string {
  const count = source.split(MARK_PLACEHOLDER).length - 1;
  if (count !== 1) throw new Error(`expected the mark placeholder once in the template, found it ${count} times`);
  return source.replace(MARK_PLACEHOLDER, `data:image/webp;base64,${mark.toString("base64")}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const source = readFileSync(`${ACCESS_DIR}login-page.src.html`, "utf8");
  const mark = readFileSync(`${ACCESS_DIR}mark.webp`);
  const page = buildAccessPage(source, mark);
  writeFileSync(`${ACCESS_DIR}login-page.html`, page);
  console.log(`access/login-page.html: ${page.length} characters`);
}
