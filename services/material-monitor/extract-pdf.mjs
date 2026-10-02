import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

try {
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 12_000_000) throw new Error("Too large");
    chunks.push(chunk);
  }
  const task = getDocument({ data: new Uint8Array(Buffer.concat(chunks)), useWorkerFetch: false, useSystemFonts: false, disableFontFace: true, stopAtErrors: true, verbosity: 0 });
  const pdf = await task.promise;
  if (pdf.numPages > 60) throw new Error("Too many pages");
  const pages = [];
  for (let number = 1; number <= pdf.numPages; number++) {
    const page = await pdf.getPage(number);
    const content = await page.getTextContent();
    const text = content.items.map(item => "str" in item ? item.str + (item.hasEOL ? "\n" : " ") : "").join("");
    if (!text.trim()) throw new Error("Scanned/empty page requires manual extraction");
    pages.push({ page: number, text });
    page.cleanup();
  }
  await task.destroy();
  process.stdout.write(JSON.stringify(pages));
} catch (error) { console.error(error instanceof Error ? error.message : "PDF parse failed"); process.exitCode = 1; }
