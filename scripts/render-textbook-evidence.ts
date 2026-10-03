import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { textbookPages, textbookSource } from "../lib/textbook-source";

// Usage: npx tsx scripts/render-textbook-evidence.ts <supplied.pdf> [pdftoppm executable]
// Regenerates four cited pages for LOCAL inspection only. Never writes to public/.
async function main() {
  const [input, renderer = "pdftoppm"] = process.argv.slice(2);
  if (!input) throw new Error("Provide the supplied Daniel and Ishai PDF path.");
  const pdf = path.resolve(input);
  const hash = (data: Buffer) => createHash("sha256").update(data).digest("hex");
  if (hash(await readFile(pdf)) !== textbookSource.sha256) throw new Error("This PDF does not match the reviewed textbook edition and fingerprint.");
  const output = path.resolve(".local", "textbook-evidence", textbookSource.id);
  await mkdir(output, { recursive: true });
  const pages = [];
  for (const page of textbookPages) {
    const destination = path.join(output, `page-${page.pdfPage}.png`);
    execFileSync(renderer, ["-f", String(page.pdfPage), "-l", String(page.pdfPage), "-singlefile", "-scale-to", "2800", "-png", pdf, destination.slice(0, -4)], { windowsHide: true });
    const bytes = await readFile(destination);
    pages.push({ ...page, sha256: hash(bytes), width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) });
  }
  const manifest = { sourceId: textbookSource.id, sourceTitle: textbookSource.title, sourceSha256: textbookSource.sha256,
    method: "Uncropped original PDF pages rendered to PNG with Poppler; no table reconstruction or numerical editing.", pages };
  await writeFile(path.join(output, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Rendered ${pages.length} source pages for local inspection in ${output}.`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
