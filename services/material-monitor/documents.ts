import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { load } from "cheerio";
import type { Source } from "./sources";

export type PageText = { page: number; text: string };
export type Document = { url: string; bytes: Uint8Array; pages: PageText[] };
export const hash = (input: string | Uint8Array) => createHash("sha256").update(input).digest("hex");
export const normalize = (text: string) => text.normalize("NFKC").replace(/\s+/g, " ").trim();
export const textHash = (pages: PageText[]) => hash(pages.map(p => normalize(p.text)).join("\n"));

export function allowedUrl(value: string, source: Source): URL {
  const url = new URL(value);
  if (url.protocol !== "https:" || url.username || url.password ||
      (url.port && url.port !== "443") || !source.hosts.includes(url.hostname)) {
    throw new Error("Source URL is outside this publisher's allowlist");
  }
  return url;
}

// Always re-check redirects. Never fetch arbitrary URLs found in a source document.
export async function download(value: string, source: Source, limit: number, pdf = false): Promise<Uint8Array> {
  let url = allowedUrl(value, source);
  const signal = AbortSignal.timeout(25_000);
  for (let redirects = 0; redirects <= 4; redirects++) {
    const response = await fetch(url, {
      redirect: "manual", signal,
      headers: { "User-Agent": "Anisotropy-MaterialMonitor/0.1 (public-source revision check)", Accept: pdf ? "application/pdf" : "text/html" },
    });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const location = response.headers.get("location");
      await response.body?.cancel();
      if (!location) throw new Error("Publisher redirect has no destination");
      url = allowedUrl(new URL(location, url).href, source);
      continue;
    }
    if (!response.ok) {
      await response.body?.cancel();
      throw new Error(`Publisher returned HTTP ${response.status}`);
    }
    if (Number(response.headers.get("content-length")) > limit) {
      await response.body?.cancel();
      throw new Error("Source exceeds the download size limit");
    }
    if (!response.body) throw new Error("Publisher returned an empty body");
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let length = 0;
    try {
      while (true) {
        const { value: chunk, done } = await reader.read();
        if (done) break;
        length += chunk.length;
        if (length > limit) throw new Error("Source exceeds the download size limit");
        chunks.push(chunk);
      }
    } finally { await reader.cancel(); }
    const bytes = Buffer.concat(chunks);
    if (pdf && bytes.subarray(0, 5).toString() !== "%PDF-") throw new Error("Expected a PDF; received another format");
    return bytes;
  }
  throw new Error("Publisher redirected too many times");
}

export function discoverDocument(html: string, source: Source): string {
  const $ = load(html);
  const candidates = new Set<string>();
  $("a[href]").each((_, element) => {
    const href = $(element).attr("href");
    if (!href) return;
    const url = new URL(href, source.pageUrl);
    if (source.documentPattern.test(url.pathname)) candidates.add(allowedUrl(url.href, source).href);
  });
  if (candidates.size !== 1) throw new Error(`Expected one matching datasheet; found ${candidates.size}. Adapter review required.`);
  return [...candidates][0];
}

export function extractStandardMetadata(html: string, source: Source): { edition: string; catalogUpdated: string | null } {
  if (!source.standardCode) throw new Error("Missing standard identity");
  const $ = load(html);
  $("script,style,noscript").remove();
  const body = normalize($("body").text());
  const code = source.standardCode.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const matches = [...body.matchAll(new RegExp(`\\b(${code}-[A-Z0-9]+)\\s+Active\\b`, "gi"))];
  const editions = [...new Set(matches.map(m => m[1].toUpperCase()))];
  if (editions.length !== 1) throw new Error("Could not verify one active publisher edition; manual standard review required");
  const updated = normalize($(".last-updated").text()).replace(/^Last Updated:\s*/i, "");
  return { edition: editions[0], catalogUpdated: updated || null };
}

// Parse untrusted PDF bytes in a disposable process with time/output/memory bounds.
export function extractPdf(bytes: Uint8Array): Promise<PageText[]> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["--max-old-space-size=256", fileURLToPath(new URL("./extract-pdf.mjs", import.meta.url))], { windowsHide: true, stdio: ["pipe", "pipe", "pipe"] });
    let output = "";
    let failed = false;
    const fail = (error: Error) => { failed = true; child.kill(); reject(error); };
    const timer = setTimeout(() => fail(new Error("PDF extraction timed out")), 30_000);
    child.stdout.on("data", chunk => {
      output += chunk.toString();
      if (output.length > 2_000_000) fail(new Error("PDF extraction exceeded the text limit"));
    });
    child.stderr.on("data", () => { /* Do not expose parser internals or document content in logs. */ });
    child.stdin.on("error", () => { /* Process close reports failures. */ });
    child.on("error", error => { clearTimeout(timer); fail(error); });
    child.on("close", code => {
      clearTimeout(timer);
      if (failed) return;
      if (code !== 0) return reject(new Error("PDF extraction failed; manual review required"));
      try { resolve(JSON.parse(output)); } catch { reject(new Error("Invalid PDF extraction output")); }
    });
    child.stdin.end(bytes);
  });
}

export async function retrieveDocument(source: Source): Promise<Document> {
  if (source.kind === "reference-document") {
    const bytes = await download(source.pageUrl, source, source.maxDocumentBytes ?? 12_000_000, true);
    // Byte fingerprint only: this is a revision event, never a property extraction.
    return { url: source.pageUrl, bytes, pages: [{ page: 1, text: JSON.stringify({ documentFingerprint: hash(bytes) }) }] };
  }
  const html = Buffer.from(await download(source.pageUrl, source, 3_000_000)).toString("utf8");
  if (source.kind === "standard-metadata") {
    const data = extractStandardMetadata(html, source);
    const text = JSON.stringify(data);
    return { url: source.pageUrl, bytes: Buffer.from(text), pages: [{ page: 1, text }] };
  }
  const url = discoverDocument(html, source);
  const bytes = await download(url, source, 12_000_000, true);
  const pages = await extractPdf(bytes);
  const text = pages.map(p => normalize(p.text)).join(" ");
  if (!pages.length || text.length < 100 || !source.identity.every(pattern => pattern.test(text))) {
    throw new Error("Extracted document did not pass material identity/text checks; manual review required");
  }
  return { url, bytes, pages };
}

export function changedPages(before: PageText[], after: PageText[]) {
  const numbers = [...new Set([...before, ...after].map(p => p.page))].sort((a, b) => a - b);
  return numbers.flatMap(page => {
    const oldText = before.find(p => p.page === page)?.text || "";
    const newText = after.find(p => p.page === page)?.text || "";
    return normalize(oldText) === normalize(newText) ? [] : [{ page, before: oldText, after: newText }];
  });
}
