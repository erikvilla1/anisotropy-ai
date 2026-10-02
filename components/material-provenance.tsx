"use client";
import { useEffect, useState } from "react";
import publishedReferences from "@/lib/published-material-references.json";
import { downloadFile } from "@/lib/demo";
import { ArrowUpRight } from "lucide-react";
import { materialEvidence, standards, type MaterialFeed, type PropertyValue, type SourceStatus } from "@/lib/material-evidence";
import { PropertyTable } from "./property-table";

export function referenceRelease(id: string, feed: MaterialFeed | null) {
  return feed?.releases.find(r => r.materialId === id) || (publishedReferences as MaterialFeed["releases"]).find(r => r.materialId === id);
}

export function useMaterialFeed() {
  const [feed, setFeed] = useState<MaterialFeed | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    let active = true;
    let running = false;
    const controller = new AbortController();
    async function refresh() {
      if (running) return;
      running = true;
      try {
        const response = await fetch("/materials/catalog-status.json", { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]) });
        if (!response.ok) throw new Error("Unavailable");
        const data = await response.json();
        if (data.schemaVersion !== 1 || !Number.isFinite(Date.parse(data.generatedAt)) || !Array.isArray(data.sources) || !Array.isArray(data.candidates) || !Array.isArray(data.releases)) throw new Error("Invalid feed");
        if (active) { setFeed(data); setUnavailable(false); }
      } catch { if (active) setUnavailable(true); }
      finally { running = false; }
    }
    void refresh();
    const timer = setInterval(refresh, 30_000);
    return () => { active = false; controller.abort(); clearInterval(timer); };
  }, []);
  const stale = unavailable || !feed || Date.now() - Date.parse(feed.generatedAt) > 180_000;
  return { feed, stale };
}

export function displayDate(value: string | null | undefined) {
  if (!value) return "Not verified";
  if (/^\d{4}-\d{2}$/.test(value)) return new Date(`${value}-01T12:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T12:00:00Z`).toLocaleDateString("en-US", { dateStyle: "medium", timeZone: "UTC" });
  return new Date(value).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}
function sourceState(source: SourceStatus, stale: boolean) {
  if (source.failed) return "Latest check failed";
  if (!source.lastSuccess) return "Not yet checked";
  if (stale) return "Monitor status unavailable";
  if (Date.now() > Date.parse(source.nextCheck)) return "Update check overdue";
  return source.review === "accepted" ? "Source reviewed" : source.review === "rejected" ? "Source rejected" : "Source review pending";
}

export function ReferenceProperties({ properties, url }: { properties: PropertyValue[]; url: string | null }) {
  return <div className="table-scroll provenance-values"><table>
    <thead><tr><th>Property / direction</th><th>Value</th><th>Basis</th><th>Method in source</th><th>Conditions / evidence</th></tr></thead>
    <tbody>{properties.map(p => <tr key={p.key} className={p.review ? "flagged-property" : ""}><td>{p.label}<small>{p.direction}</small></td><td>{p.value} {p.unit}{p.review && <small className="property-review">{p.review}</small>}</td><td>{p.basis === "nominal" ? "Nominal / typical" : "Supplier minimum"}</td><td>{p.method}</td><td>{p.conditions}<small>{url ? <a href={`${url}#page=${p.sourcePage}`} target="_blank" rel="noreferrer">Source page {p.sourcePage} <ArrowUpRight size={11} /></a> : `Source page ${p.sourcePage}`} · {p.evidence}</small></td></tr>)}</tbody>
  </table></div>;
}

export function MaterialProvenance({ id, feed, stale }: { id: string; feed: MaterialFeed | null; stale: boolean }) {
  const evidence = materialEvidence[id];
  const sources = evidence.sourceIds.map(sourceId => feed?.sources.find(s => s.id === sourceId)).filter((s): s is SourceStatus => !!s);
  const release = referenceRelease(id, feed);
  const source = sources[0];
  const needsUpdate = release && sources.some(s => s.fingerprint !== release.fingerprint && s.id === release.sourceId);
  const label = evidence.identity === "identity-needed" ? "Identity needed" : evidence.identity === "confirmation-needed" ? "Source match required" : release ? "Reviewed reference" : "Property review needed";
  return <details className="material-provenance" aria-label="Source and standards traceability"><summary>Sources, revisions &amp; test standards</summary>
    <p className="library-monitor-status" role="status">{stale ? "Live monitor unavailable — last known evidence only" : "Revision monitoring connected · refreshes automatically"}</p>
    <div className="provenance-status"><span className="provenance-chip">{label}</span><span>Engineering reference · applicability depends on the dataset</span></div>
    <p className="provenance-issue">{evidence.issue}</p>
    <dl className="provenance-dates">
      <div><dt>Latest observed source revision</dt><dd>{source?.revision || "Not verified"}</dd></div>
      <div><dt>Source revision date</dt><dd>{displayDate(source?.revisionDate)}</dd></div>
      <div><dt>Last successful source check</dt><dd>{displayDate(source?.lastSuccess)}</dd></div>
      <div><dt>Manufacturer reference checked</dt><dd>{release ? displayDate(release.approvedAt) : "No checked manufacturer dataset"}</dd></div>
    </dl>
    {source && <p className="provenance-caption">{source.dateMeaning} A successful check does not establish engineering validity.</p>}
    {needsUpdate && <p className="source-review">A different source document has been detected. The approved reference stays pinned to its original revision until a replacement is reviewed.</p>}
    <div className="provenance-sources">
      <h3>Original sources</h3>
      {evidence.references.length ? evidence.references.map(ref => <div key={ref.url}><a href={ref.url} target="_blank" rel="noreferrer">{ref.title} <ArrowUpRight size={13} /></a><p>{ref.relationship}</p></div>) : <p>No exact manufacturer source can be assigned until the material identity is supplied.</p>}
      {sources.map(s => <div key={s.id} className="source-observation"><strong>{s.name}</strong><span>{sourceState(s, stale)}</span><p>{s.documentUrl && <a href={s.documentUrl} target="_blank" rel="noreferrer">Publisher document <ArrowUpRight size={12} /></a>} {s.fingerprint && <> · Fingerprint {s.fingerprint.slice(0, 12)}</>}</p></div>)}
      {sources.some(s => s.propertyExtraction === "review-required") && <p className="source-review">The latest document's table or conditions could not be verified automatically. Property extraction is blocked pending review.</p>}
      {!evidence.sourceIds.length && <p className="provenance-caption">Material datasheet monitoring is not configured: source identity or supplier confirmation is needed.</p>}
      {!!evidence.sourceIds.length && !sources.length && <p className="provenance-caption">Source registered; monitoring results are currently unavailable.</p>}
    </div>
    <details className="standard-references"><summary>Test methods & standard revision tracking</summary>
      <p>These are relevant methods to investigate, not proof that the classroom values were tested to them. A property row identifies its actual reported method separately. A newer edition does not change an existing measurement.</p>
      {evidence.methodIds.map(key => { const standard = standards[key]; const observation = feed?.sources.find(s => s.id === standard.monitorId); return <div className="standard-reference" key={key}><a href={standard.url} target="_blank" rel="noreferrer">{standard.title} <ArrowUpRight size={12} /></a><small>{observation?.revision ? `Latest observed active edition: ${observation.revision}` : "Active edition not verified"}</small><small>{observation ? `Catalog last updated: ${displayDate(observation.revisionDate)} · Last successful check: ${displayDate(observation.lastSuccess)}` : "Publisher reference available; automatic edition monitoring not connected."}</small>{observation && <small>{observation.failed ? "Latest check failed — inspect publisher before use" : stale ? "Monitor status unavailable" : Date.now() > Date.parse(observation.nextCheck) ? "Check overdue" : observation.review === "pending" ? "Edition impact review pending" : `Edition review: ${observation.review}`}</small>}</div>; })}
      <p><a href="https://www.cmh17.org/" target="_blank" rel="noreferrer">CMH-17</a> provides the characterization/allowables framework. <a href="https://www.wichita.edu/industry_and_defense/NIAR/Research/ncamp.php" target="_blank" rel="noreferrer">NCAMP</a> is a qualification-data resource; inclusion of these links does not establish that this material has an applicable qualified dataset.</p>
    </details>
  </details>;
}

export function ManufacturerProperties({ id, feed }: { id: string; feed: MaterialFeed | null }) {
  const release = referenceRelease(id, feed);
  const candidate = feed?.candidates.find(c => c.materialId === id);
  const source = feed?.sources.find(s => s.id === (release?.sourceId || candidate?.sourceId));
  if (!release && !candidate) return null;
  return <section className="manufacturer-properties" aria-label="Manufacturer properties">
    {release && <>
      <div className="property-reference"><span>Reference</span><a href={`${release.documentUrl}#page=${release.properties[0]?.sourcePage || 1}`} target="_blank" rel="noreferrer">{materialEvidence[id].references[0]?.title || "Manufacturer datasheet"} · PDF <ArrowUpRight size={14}/></a><small>{release.sourceRevision || "Revision not stated"} · {release.sourceRevisionDate ? `Published ${displayDate(release.sourceRevisionDate)}` : "Publication date not stated"}</small></div>
      <p className="dataset-context">{[...new Set(release.properties.map(p => p.conditions))].join(". ")}</p>
      <PropertyTable properties={release.properties.map(p => ({ key: p.key, label: p.label, value: p.value, unit: p.unit, context: `${p.direction} · ${p.basis === "minimum" ? "Minimum" : "Typical"}`, note: p.review }))}/>
      <p className="units-note">Typical values describe representative performance. Minimum values are the supplier's stated limits.</p>
      <details className="reference-methods"><summary>Test methods &amp; reference notes</summary><p>Use the reported material, direction and conditions. Supplier values are not statistical design allowables.</p><ReferenceProperties properties={release.properties} url={release.documentUrl}/><p className="provenance-caption">Added {displayDate(release.approvedAt)} · Reference {release.releaseId}</p></details>
      <button className="text-button" onClick={() => downloadFile(`${id}-manufacturer-properties.json`, JSON.stringify({ ...release, use: "engineering-reference", designAllowables: false, note: "Source transcription verified; analyst must establish applicability. This is a property dataset, not necessarily a complete material model.", properties: release.properties.filter(p => !p.review), excludedProperties: release.properties.filter(p => p.review).map(p => ({ key: p.key, label: p.label, reason: p.review })) }, null, 2), "application/json")}>Export manufacturer properties</button>
    </>}
    {candidate && candidate.fingerprint !== release?.fingerprint && <details className="candidate-properties"><summary>New manufacturer values · awaiting source verification</summary><p>These newly extracted values are pending verification. Previously checked values remain unchanged.</p><ReferenceProperties properties={candidate.properties} url={source?.documentUrl || null} /></details>}
  </section>;
}
