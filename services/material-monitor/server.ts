import { createServer, type IncomingMessage } from "node:http";
import { randomBytes } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { sources } from "./sources";
import { MonitorStore } from "./store";
import { runChecks } from "./worker";
import { buildCatalog, publishReference, writeCatalog } from "./catalog";

const port = Number(process.env.MATERIAL_MONITOR_PORT || 3210);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Invalid monitor port");
const store = new MonitorStore(resolve(process.env.MATERIAL_MONITOR_DB || ".local/material-monitor/monitor.sqlite"), sources);
const token = randomBytes(32).toString("hex");
let busy = false;
let workerError: string | null = null;

async function check(force: boolean) {
  if (busy) return;
  busy = true;
  workerError = null;
  try { await runChecks(store, force); }
  catch (error) { workerError = error instanceof Error ? error.message : "Worker failed"; }
  finally {
    try { writeCatalog(store); } catch { workerError = "Could not refresh the public library feed"; }
    busy = false;
  }
}

async function body(request: IncomingMessage) {
  let text = "";
  for await (const chunk of request) {
    text += chunk.toString();
    if (text.length > 8000) throw new Error("Request body too large");
  }
  return JSON.parse(text);
}

if (process.argv.includes("--once")) {
  runChecks(store, process.argv.includes("--force"))
    .then(results => { writeCatalog(store); console.log(JSON.stringify(results, null, 2)); if (results.some(r => r.outcome === "failed")) process.exitCode = 1; })
    .catch(error => { console.error(error.message); process.exitCode = 1; })
    .finally(() => store.close());
} else {
  const server = createServer(async (request, response) => {
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("X-Content-Type-Options", "nosniff");
    response.setHeader("Referrer-Policy", "no-referrer");
    response.setHeader("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
    const send = (status: number, value: unknown) => { response.writeHead(status, { "Content-Type": "application/json" }); response.end(JSON.stringify(value)); };
    const hosts = [`127.0.0.1:${port}`, `localhost:${port}`];
    if (!hosts.includes(request.headers.host || "") || request.headers["sec-fetch-site"] === "cross-site") return send(403, { error: "Local console requests only" });
    const origin = request.headers.origin;
    if (origin && !hosts.some(host => origin === `http://${host}`)) return send(403, { error: "Origin not allowed" });
    const url = new URL(request.url || "/", `http://127.0.0.1:${port}`);
    try {
      if (request.method === "GET" && ["/", "/console.js", "/console.css"].includes(url.pathname)) {
        const file = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
        response.writeHead(200, { "Content-Type": file.endsWith(".html") ? "text/html; charset=utf-8" : file.endsWith(".js") ? "text/javascript; charset=utf-8" : "text/css; charset=utf-8" });
        response.end(await readFile(new URL(`./ui/${file}`, import.meta.url)));
      } else if (request.method === "GET" && url.pathname === "/api/status") {
        send(200, { sources: store.list(), busy, workerError, token, schedule: "Daily source checks while this service is running. Failed checks retry with backoff. No external notifications configured." });
      } else if (request.method === "GET" && url.pathname === "/api/source") {
        send(200, store.detail(url.searchParams.get("id") || ""));
      } else if (request.method === "GET" && url.pathname === "/api/catalog") {
        send(200, buildCatalog(store));
      } else if (request.method === "GET" && url.pathname === "/api/document") {
        const snapshot = store.snapshot(Number(url.searchParams.get("id")));
        if (!snapshot) return send(404, { error: "Document not found" });
        const metadata = store.source(snapshot.source_id).kind === "standard-metadata";
        response.writeHead(200, { "Content-Type": metadata ? "application/json" : "application/pdf", "Content-Disposition": `attachment; filename="${snapshot.source_id}-${snapshot.id}.${metadata ? "json" : "pdf"}"` });
        response.end(snapshot.bytes);
      } else if (request.method === "POST") {
        if (request.headers["x-monitor-token"] !== token || !request.headers["content-type"]?.startsWith("application/json")) return send(403, { error: "Reload the local console before making changes" });
        if (url.pathname === "/api/check") {
          if (busy) return send(409, { error: "A check is already running" });
          void check(true);
          send(202, { message: "Source check started" });
        } else if (url.pathname === "/api/review") {
          if (busy) return send(409, { error: "Wait for the active source check before reviewing" });
          const data = await body(request);
          store.review(data.snapshotId, data.decision, data.reviewer, data.note);
          writeCatalog(store);
          send(200, { message: "Source review recorded. No material property values were published." });
        } else if (url.pathname === "/api/publish-reference") {
          if (busy) return send(409, { error: "Wait for the active source check before publishing" });
          const data = await body(request);
          const release = publishReference(store, data.materialId, data.fingerprint, data.reviewer, data.note);
          writeCatalog(store);
          send(200, { message: "Reference revision published. These values remain ineligible for design calculations.", releaseId: release.releaseId });
        } else send(404, { error: "Not found" });
      } else send(404, { error: "Not found" });
    } catch (error) {
      send(400, { error: error instanceof Error ? error.message : "Request failed" });
    }
  });
  server.requestTimeout = 15_000;
  server.on("error", error => { console.error(error.message); store.close(); process.exitCode = 1; });
  server.listen(port, "127.0.0.1", () => {
    console.log(`Material review console: http://127.0.0.1:${port}`);
    console.log("Local operator access only. Not a production authentication or compliance boundary.");
    void check(false);
  });
  const timer = setInterval(() => { void check(false); }, 60_000);
  timer.unref();
  const stop = () => { clearInterval(timer); server.close(() => { store.close(); process.exit(0); }); };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
}
