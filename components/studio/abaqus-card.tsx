"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Upload as UploadIcon } from "lucide-react";
import {
  cancelUploadKey, cardRows, cardText, compareAgain, connectorCommand, connectorUrl, createUploadKey, differences, documentProblem, documentUrl, getExchange, getUpload,
  headline, KEY_FILE,
  listUploadKeys, listUploads, megabytes, notComparedWords, percent, provenance, quantityName, removeUpload, sendProblem, sendUpload, sentFileUrl, writeDocument,
  type Comparison, type Exchange, type NewUploadKey, type Refusal, type SendStage, type Upload, type UploadKey,
} from "@/lib/abaqus-exchange";
import { fileUrl, type Fields, type JobStatus } from "@/lib/studio-api";
import { printed } from "@/lib/studio-colors";
import { downloadName } from "@/lib/studio-copy";
import { namingOf } from "./job-files";

const WAIT_MS = 5000; // how often the card looks for a file sent straight from Abaqus, while its instructions are open
const ZONE_WORDS: Record<string, string> = { gauge: "Gauge section", "free length": "Between gauge and tabs", band: "Within one width of a tab", "tab line": "At a tab line",
  gripped: "Under the grips" };
const when = (iso: string | null): string => {
  const date = iso ? new Date(iso) : null;
  return date && !Number.isNaN(date.getTime()) ? date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
};
const kilobytes = (bytes: number): string => (bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} kB`);

type Busy = { what: SendStage | "again" | "removing" | "document"; fraction: number } | null;
type Problem = { words: string; reasons: string[] } | null;

/** The card of the user's own Abaqus on a finished run (ADR-0094 part 7, step 6): the answer first ("Agrees with ours", or in how many
 * places it differs), then the model, the pull force, the gauge section and between gauge and tabs; a difference where it is; the detail on
 * request. Without a file yet, the three steps to one: the build script to open in Abaqus/CAE, the connector, and a place to drop the file
 * it writes; where the API takes it, an upload key so the connector sends the file itself. The file is its owner's alone. Every number is
 * the fea package's, read from the upload's row (ADR-0001). This card and its downloads may name Abaqus (`ABAQUS_CARD_ALLOWS`); the rest of
 * the page still does not. */
export function AbaqusCard({ apiBase, job, fields, onShow }: {
  apiBase: string; job: JobStatus; fields: Fields; onShow: (element: number, ply: number, criterion: string, face?: string | null) => void;
}) {
  const [exchange, setExchange] = useState<Exchange | null>(null);
  const [upload, setUpload] = useState<Upload | null>(null);
  const [earlier, setEarlier] = useState<Upload[]>([]);
  const [busy, setBusy] = useState<Busy>(null);
  const [problem, setProblem] = useState<Problem>(null);
  const [waiting, setWaiting] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const jobId = job.job_id;

  /** The newest of the requester's files beside this run, with its comparison; the older ones by their date. */
  const load = useCallback(async (signal?: AbortSignal) => {
    const all = await listUploads(apiBase, jobId, signal);
    setEarlier(all.slice(1));
    setUpload(all.length ? await getUpload(apiBase, all[0].id, signal) : null);
    return all;
  }, [apiBase, jobId]);

  useEffect(() => {
    const controller = new AbortController();
    setExchange(null); setUpload(null); setEarlier([]); setProblem(null);
    (async () => {
      const offered = await getExchange(apiBase, controller.signal);
      if (controller.signal.aborted || !offered?.uploads) return;
      setExchange(offered);
      await load(controller.signal);
    })().catch(() => undefined); // an API that does not answer here offers no card; the run's own results stand
    return () => controller.abort("replaced");
  }, [apiBase, jobId, load]);

  const newest = upload?.id ?? null;
  useEffect(() => {
    if (!waiting || !exchange) return;
    const timer = window.setInterval(() => {
      listUploads(apiBase, jobId).then((all) => { if (all.length && all[0].id !== newest) { setWaiting(false); setProblem(null); void load(); } }).catch(() => undefined);
    }, WAIT_MS);
    return () => window.clearInterval(timer);
  }, [waiting, exchange, apiBase, jobId, newest, load]);

  if (!exchange) return null;

  async function send(file: File | undefined | null) {
    if (!file || busy || !exchange) return;
    setProblem(null);
    if (file.size > exchange.max_bundle_bytes) {
      setProblem({ words: `This file is ${kilobytes(file.size)}, larger than ${megabytes(exchange.max_bundle_bytes)}, the most that can be sent.`, reasons: [] });
      return;
    }
    setBusy({ what: "sending", fraction: 0 });
    try {
      const sent = await sendUpload(apiBase, jobId, file, (what, fraction) => setBusy({ what, fraction }));
      setEarlier((list) => (upload ? [upload, ...list] : list));
      setUpload(sent);
    } catch (error) {
      setProblem(sendProblem(error, exchange));
    } finally {
      setBusy(null);
      if (input.current) input.current.value = "";
    }
  }

  async function again() {
    if (!upload || busy || !exchange) return;
    setProblem(null); setBusy({ what: "again", fraction: 1 });
    try { setUpload(await compareAgain(apiBase, upload.id, jobId)); }
    catch (error) { setProblem(sendProblem(error, exchange)); }
    finally { setBusy(null); }
  }

  /** The comparison as a PDF: written first when it is not kept yet, which the card says, then saved by the browser from its link. */
  async function print() {
    if (!upload || busy) return;
    setProblem(null); setBusy({ what: "document", fraction: 1 });
    try { await writeDocument(apiBase, upload.id); window.location.assign(documentUrl(apiBase, upload.id)); }
    catch (error) { setProblem(documentProblem(error)); }
    finally { setBusy(null); }
  }

  async function remove() {
    if (!upload || busy || !exchange) return;
    setProblem(null); setBusy({ what: "removing", fraction: 1 });
    try { await removeUpload(apiBase, upload.id); await load(); }
    catch (error) { setProblem(sendProblem(error, exchange)); }
    finally { setBusy(null); }
  }

  async function open(id: string) {
    if (busy) return;
    setProblem(null);
    try {
      const picked = await getUpload(apiBase, id);
      setEarlier((list) => [...(upload ? [upload] : []), ...list.filter((u) => u.id !== id)].sort((a, b) => b.created_at.localeCompare(a.created_at)));
      setUpload(picked);
    } catch (error) { setProblem(sendProblem(error, exchange!)); }
  }

  const comparison = upload?.comparison ?? null;
  const said = comparison ? headline(comparison) : null;
  const naming = namingOf(fields);
  const buildName = downloadName("abaqus_build", naming);
  const busyWords = busy === null ? null
    : busy.what === "sending" ? `Sending your file… ${Math.round(100 * busy.fraction)} %`
      : busy.what === "comparing" ? "Reading your model and comparing it with this run…"
        : busy.what === "again" ? "Comparing again…" : busy.what === "document" ? "Writing the PDF…" : "Removing the file…";
  const chooser = (label: string, primary: boolean) => (
    <button type="button" className={primary ? "studio-button" : "studio-text-button"} disabled={busy !== null} onClick={() => input.current?.click()} data-testid={primary ? "abaqus-choose" : "abaqus-send-another"}>
      {primary ? <UploadIcon size={13} aria-hidden="true" /> : null} {label}
    </button>
  );

  return (
    <div className="studio-panel studio-abaqus" data-testid="abaqus-card" data-names-abaqus="true" data-verdict={upload?.verdict ?? (upload ? "not-compared" : "none")}>
      <input ref={input} type="file" accept=".zip,application/zip" hidden aria-label="The file the connector wrote" data-testid="abaqus-file"
        onChange={(e) => void send(e.target.files?.[0])} />
      {upload ? (
        <>
          <h3>Your Abaqus model {said ? <span className={`studio-badge studio-abaqus-${said.tone}`} data-testid="abaqus-verdict">{said.words}</span>
            : <span className="studio-badge studio-abaqus-open" data-testid="abaqus-verdict">Not compared</span>}</h3>
          {comparison && comparison.verdict !== "refused" ? <Compared comparison={comparison} upload={upload} fields={fields} onShow={onShow} />
            : <NotCompared upload={upload} refusal={comparison} />}
          {busyWords ? <p className="studio-status" role="status" data-testid="abaqus-progress">{busyWords}</p> : null}
          {problem ? <Trouble problem={problem} /> : null}
          <p className="studio-abaqus-actions">
            <button type="button" className="studio-text-button" disabled={busy !== null} onClick={() => void again()} data-testid="abaqus-again">Compare again</button>
            {comparison && comparison.verdict !== "refused" ? (
              <button type="button" className="studio-text-button" disabled={busy !== null} onClick={() => void print()} data-testid="abaqus-document"><Download size={12} aria-hidden="true" /> The comparison as a PDF</button>
            ) : null}
            <a className="studio-text-button" href={sentFileUrl(apiBase, upload.id)} target="_blank" rel="noreferrer" data-testid="abaqus-sent-file"><Download size={12} aria-hidden="true" /> The file you sent</a>
            {chooser("Send another file", false)}
            <button type="button" className="studio-text-button" disabled={busy !== null} onClick={() => void remove()} data-testid="abaqus-remove">Remove</button>
          </p>
          {earlier.length ? (
            <p className="studio-muted" data-testid="abaqus-earlier">Sent earlier for this run:{" "}
              {earlier.map((u) => <button key={u.id} type="button" className="studio-text-button" onClick={() => void open(u.id)}>{u.job ?? "a model"}, {when(u.created_at)}</button>)}</p>
          ) : null}
          <p className="studio-muted">Sent {when(upload.created_at)}. The file is yours: only you and the Anisotropy team can see it. Remove deletes it.</p>
        </>
      ) : (
        <>
          <h3>Compare with your Abaqus model</h3>
          <p>Solve this coupon in your own Abaqus and send the result here. The model, the pull force and every ply&apos;s stresses and strains are compared with this run.</p>
          <ol className="studio-abaqus-steps">
            <li>
              <strong>Open in Abaqus/CAE.</strong>{" "}
              {"abaqus_build" in job.outputs ? (
                <><a href={fileUrl(apiBase, jobId, "abaqus_build", buildName)} download={buildName} target="_blank" rel="noreferrer" data-testid="abaqus-build"><Download size={12} aria-hidden="true" /> Build script</a>.
                  {" "}In Abaqus/CAE choose File, Run Script. It builds this coupon as a model you can edit, with a job ready to submit.</>
              ) : <>In Abaqus/CAE choose File, Import, Model and pick the solver input from this run&apos;s files.</>}
            </li>
            <li>
              <strong>Run the job, then the connector.</strong>{" "}
              <a href={connectorUrl(apiBase)} download="anisotropy-connector.zip" target="_blank" rel="noreferrer" data-testid="abaqus-connector"><Download size={12} aria-hidden="true" /> Connector (ZIP)</a>.
              {" "}Unzip it beside your job and run <code>abaqus python anisotropy_connector.py &lt;your job&gt;.odb --units {fields.units === "m-Pa" ? "m-Pa" : "mm-MPa"}</code>.
              {" "}It writes one file, &lt;your job&gt;-anisotropy.zip, and sends nothing.
              {" "}<span data-testid="abaqus-connector-more">Its README also shows how to add an Anisotropy menu to Abaqus/CAE and how to send every job as it finishes.</span>
            </li>
            <li>
              <strong>Send to Anisotropy.</strong>
              <div className="studio-abaqus-drop" data-over={over} data-testid="abaqus-drop"
                onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
                onDrop={(e) => { e.preventDefault(); setOver(false); void send(e.dataTransfer.files?.[0]); }}>
                <span>Drop &lt;your job&gt;-anisotropy.zip here, or</span> {chooser("Choose the file", true)}
              </div>
            </li>
          </ol>
          {busyWords ? <p className="studio-status" role="status" data-testid="abaqus-progress">{busyWords}</p> : null}
          {problem ? <Trouble problem={problem} /> : null}
          <p className="studio-muted">The file is yours: only you and the Anisotropy team can see it, and you can remove it at any time. At most {megabytes(exchange.max_bundle_bytes)}.</p>
        </>
      )}
      {exchange.connector_route ? (
        <UploadKeys apiBase={apiBase} job={job} units={fields.units} limit={exchange.max_tokens} waiting={waiting} onOpen={setWaiting} />
      ) : null}
    </div>
  );
}

function Trouble({ problem }: { problem: NonNullable<Problem> }) {
  return (
    <div className="studio-alert" role="alert" data-testid="abaqus-problem">
      <p>{problem.words}</p>
      {problem.reasons.length ? <details><summary>Why</summary><ul>{problem.reasons.map((r) => <li key={r}>{r}</li>)}</ul></details> : null}
    </div>
  );
}

/** A file that is stored and stands beside nothing yet: why, in plain words, and what the reader of the model could not take. */
function NotCompared({ upload, refusal }: { upload: Upload; refusal: Refusal | null }) {
  const facts = upload.facts ?? {};
  const unread = ["deck", "every_output", "reactions", "model"].map((key) => (facts[key] as { read?: boolean; reason?: string } | null | undefined))
    .filter((part) => part && part.read === false && cardText(part.reason)).map((part) => cardText(part!.reason) as string);
  const reasons = refusal ? refusal.problems.map((p) => cardText(p)).filter((p): p is string => p !== null) : unread;
  return (
    <div data-testid="abaqus-not-compared">
      <p>{refusal ? "This model was not compared with this run, because the two are not the same coupon or it holds something the comparison does not read."
        : upload.verdict ? "This comparison was written by an older version. Click Compare again to see it." : notComparedWords(upload.not_compared)}</p>
      {reasons.length ? <details open={Boolean(refusal)}><summary>Details</summary><ul>{reasons.map((r) => <li key={r}>{r}</li>)}</ul></details> : null}
    </div>
  );
}

function Compared({ comparison, upload, fields, onShow }: { comparison: Comparison; upload: Upload; fields: Fields;
  onShow: (element: number, ply: number, criterion: string, face?: string | null) => void }) {
  const rows = cardRows(comparison), differs = differences(comparison), labels = comparison.summary.labels;
  /** Our element by its number in the mesh the page shows, so a line's place can be framed in the viewer. */
  const indexOf = (label: number | null): number => (label === null ? -1 : fields.mesh.element_labels.findIndex((l) => l.split(".").pop() === String(label)));
  const unitOf = (quantity: string) => (/^E\d\d$/.test(quantity) ? "" : ` ${labels.stress}`);
  return (
    <>
      <p data-testid="abaqus-provenance">{provenance(comparison)}</p>
      <table className="studio-table studio-abaqus-rows" data-testid="abaqus-rows">
        <tbody>
          {rows.map((row) => {
            const index = indexOf(row.element);
            return (
              <tr key={row.id} data-row={row.id} data-state={row.state}>
                <th scope="row">{row.label}</th>
                <td className="studio-wrap">{row.said}{index >= 0 && row.ply !== null ? <>{" "}<button type="button" className="studio-text-button" onClick={() => onShow(index, row.ply!, "")}>Show</button></> : null}</td>
                <td><span className={`studio-badge studio-abaqus-${row.state === "same" ? "pass" : row.state === "differs" ? "fail" : "open"}`}>{row.mark}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {differs.length ? (
        <>
          <h4>What differs</h4>
          <div className="studio-table-scroll">
            <table className="studio-table" data-testid="abaqus-differences">
              <thead><tr><th scope="col">Item</th><th scope="col">Yours</th><th scope="col">Ours</th><th scope="col">Where</th></tr></thead>
              <tbody>{differs.map((d) => <tr key={d.what}><th scope="row" className="studio-wrap">{d.what}</th><td className="studio-wrap">{d.yours}</td><td className="studio-wrap">{d.ours}</td><td>{d.where ?? "–"}</td></tr>)}</tbody>
            </table>
          </div>
        </>
      ) : null}
      <details className="studio-details" data-testid="abaqus-details">
        <summary><h4>Details</h4></summary>
        <h4>The model, item by item</h4>
        <div className="studio-table-scroll">
          <table className="studio-table" data-testid="abaqus-model">
            <thead><tr><th scope="col">Item</th><th scope="col">Yours</th><th scope="col">Ours</th><th scope="col"><span className="sr-only">State</span></th></tr></thead>
            <tbody>{comparison.model.items.map((i) => (
              <tr key={i.item} data-same={String(i.same)}><th scope="row" className="studio-wrap">{i.item}</th><td className="studio-wrap">{i.yours}</td><td className="studio-wrap">{i.ours}</td>
                <td>{i.same === null ? "shown, not judged" : i.same ? "same" : "differs"}</td></tr>
            ))}</tbody>
          </table>
        </div>
        {Object.keys(comparison.summary.zones).length ? (
          <>
            <h4>The results, zone by zone</h4>
            <div className="studio-table-scroll">
              <table className="studio-table studio-table-num" data-testid="abaqus-zones">
                <thead><tr><th scope="col">Zone</th><th scope="col">Values</th><th scope="col">Largest difference</th><th scope="col">Where</th><th scope="col">Yours</th><th scope="col">Ours</th></tr></thead>
                <tbody>{Object.entries(comparison.summary.zones).map(([zone, z]) => (
                  <tr key={zone} data-zone={zone}><th scope="row">{ZONE_WORDS[zone] ?? zone}</th><td>{z.values.toLocaleString("en-US")}</td>
                    <td>{percent(z.worst)} ({quantityName(z.quantity)})</td>
                    <td className="studio-text-cell">{z.your_element !== null ? `your element ${z.your_element}${z.layer !== null ? `, ply ${z.layer}` : ""}` : "–"}</td>
                    <td>{printed(z.yours)}{unitOf(z.quantity)}</td><td>{printed(z.ours)}{unitOf(z.quantity)}</td></tr>
                ))}</tbody>
              </table>
            </div>
            <p className="studio-muted">Twelve values of every ply of every element: three stresses and three strains in the fibre axes, Mises, Tresca, the pressure and the principal stresses.
              The gauge section and the length between gauge and tabs are judged; the zones at the tabs are shown.</p>
          </>
        ) : null}
        <p className="studio-muted" data-testid="abaqus-file-facts">The file: {kilobytes(upload.bundle_bytes)}, written {when(comparison.bundle.created)}
          {comparison.bundle.written_by.connector ? ` by ${comparison.bundle.written_by.connector}` : ""}, SHA-256 {upload.bundle_sha256.slice(0, 12)}…
          {upload.compared_at ? ` Compared ${when(upload.compared_at)}.` : ""}</p>
      </details>
    </>
  );
}

/** Sending straight from Abaqus: an upload key, shown once and saved as a file the connector reads, the command that sends, and the keys
 * there are, each to cancel. While this is open the card looks for the file to arrive. The key is never part of the command. */
function UploadKeys({ apiBase, job, units, limit, waiting, onOpen }: { apiBase: string; job: JobStatus; units: string; limit: number; waiting: boolean;
  onOpen: (open: boolean) => void }) {
  const [keys, setKeys] = useState<UploadKey[] | null>(null);
  const [created, setCreated] = useState<NewUploadKey | null>(null);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState("");
  const [address, setAddress] = useState("");
  useEffect(() => { setAddress(new URL(apiBase, window.location.href).href.replace(/\/+$/, "")); }, [apiBase]);
  useEffect(() => {
    if (!waiting || keys !== null) return;
    listUploadKeys(apiBase).then(setKeys).catch(() => setKeys([]));
  }, [waiting, keys, apiBase]);
  const live = (keys ?? []).filter((k) => !k.revoked_at);
  const command = connectorCommand({ apiAddress: address || apiBase, jobId: job.job_id, coupon: job.coupon, units });

  async function create() {
    setMessage("");
    try {
      const key = await createUploadKey(apiBase, name.trim());
      setCreated(key); setName(""); setKeys((list) => [key, ...(list ?? [])]);
    } catch (error) {
      const status = (error as { status?: number }).status;
      setMessage(status === 429 ? `You have ${limit} upload keys, the most a person may keep. Cancel one, then create another.` : "The upload key was not created. Try again.");
    }
  }
  async function cancel(id: string) {
    setMessage("");
    try {
      const cancelled = await cancelUploadKey(apiBase, id);
      setKeys((list) => (list ?? []).map((k) => (k.id === id ? cancelled : k)));
      if (created?.id === id) setCreated(null);
    } catch { setMessage("The upload key was not cancelled. Try again."); }
  }
  async function copy(what: string, text: string) {
    try { await navigator.clipboard.writeText(text); setCopied(what); } catch { setCopied(""); }
  }

  return (
    <details className="studio-details studio-abaqus-keys" data-testid="abaqus-keys" onToggle={(e) => onOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary><h4>Send straight from Abaqus</h4></summary>
      <p>With an upload key the connector sends the file itself and prints the answer in your terminal. Create a key once, save it beside the connector, and add three options to the command.</p>
      <form className="studio-abaqus-key-form" onSubmit={(e) => { e.preventDefault(); void create(); }}>
        <label htmlFor="abaqus-key-name">Where you will use it</label>
        <input id="abaqus-key-name" type="text" maxLength={100} value={name} placeholder="lab workstation" autoComplete="off" onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="studio-button" data-testid="abaqus-key-create">Create an upload key</button>
      </form>
      {created ? (
        <div className="studio-abaqus-key" data-testid="abaqus-key-created">
          <p><strong>Your upload key, shown this once.</strong> Save it as {KEY_FILE} in the connector&apos;s folder. Anyone who has it can send files in your name, so cancel it if it is lost.</p>
          <code data-testid="abaqus-key-value">{created.token}</code>
          <p className="studio-abaqus-actions">
            <a className="studio-text-button" href={`data:text/plain;charset=utf-8,${encodeURIComponent(`${created.token}\n`)}`} download={KEY_FILE} data-testid="abaqus-key-save"><Download size={12} aria-hidden="true" /> Save as {KEY_FILE}</a>
            <button type="button" className="studio-text-button" onClick={() => void copy("key", created.token)}>{copied === "key" ? "Copied" : "Copy"}</button>
          </p>
        </div>
      ) : null}
      <p>Then, where the connector and your job are:</p>
      <pre className="studio-abaqus-command" data-testid="abaqus-command"><code>{command}</code></pre>
      <p className="studio-abaqus-actions"><button type="button" className="studio-text-button" onClick={() => void copy("command", command)}>{copied === "command" ? "Copied" : "Copy the command"}</button></p>
      <p className="studio-muted">Read the line it prints: &ldquo;sent:&rdquo; with the answer, or &ldquo;not sent:&rdquo; with the reason. The file is written beside your job either way.</p>
      {waiting ? <p className="studio-status" role="status" data-testid="abaqus-waiting">Waiting for a file from Abaqus…</p> : null}
      {message ? <p className="studio-alert" role="alert">{message}</p> : null}
      {live.length ? (
        <table className="studio-table" data-testid="abaqus-key-list">
          <thead><tr><th scope="col">Upload key</th><th scope="col">Created</th><th scope="col">Last used</th><th scope="col"><span className="sr-only">Cancel</span></th></tr></thead>
          <tbody>{live.map((k) => (
            <tr key={k.id}><th scope="row" className="studio-wrap">{k.name || "unnamed"}, ending in {k.hint}</th><td>{when(k.created_at)}</td><td>{when(k.last_used_at) || "never"}</td>
              <td><button type="button" className="studio-text-button" onClick={() => void cancel(k.id)}>Cancel</button></td></tr>
          ))}</tbody>
        </table>
      ) : null}
    </details>
  );
}
