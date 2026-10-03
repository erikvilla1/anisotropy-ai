"use client";
import { ArrowDownToLine, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { exportCitedMaterial, materialDatasets, referenceUrl, type CitedMaterial } from "@/lib/curated-materials";
import type { MaterialFeed } from "@/lib/material-evidence";
import { downloadFile } from "@/lib/demo";
import { propertyDisplayValue } from "@/lib/property-units";
import { PropertyTable } from "./property-table";

function date(value: string) {
  if (/^\d{4}$/.test(value)) return value;
  const month = /^\d{4}-\d{2}$/.test(value);
  return new Date(`${value}${month ? "-01" : ""}T12:00:00Z`).toLocaleDateString("en-US", month ? { month: "long", year: "numeric", timeZone: "UTC" } : { dateStyle: "medium", timeZone: "UTC" });
}

export function CitedMaterialProperties({ material: initial, feed, stale }: { material: CitedMaterial; feed: MaterialFeed | null; stale: boolean }) {
  const datasets = materialDatasets(initial);
  const [selected, setSelected] = useState(initial.datasetId);
  const material = datasets.find(d => d.datasetId === selected) || initial;
  const { source } = material;
  const references = [source, ...(material.supportingReferences || [])];
  const observations = references.map(ref => feed?.sources.find(s => s.id === ref.id));
  const changed = references.some((ref, i) => ref.sha256 ? observations[i]?.fingerprint && ref.sha256 !== observations[i]?.fingerprint : observations[i]?.outcome === "changed");
  const unavailable = stale || observations.some(o => !o?.lastSuccess);
  const failed = observations.some(o => o?.failed);
  const overdue = observations.some(o => o && Date.now() > Date.parse(o.nextCheck));
  return <div className="material-properties cited-properties">
    {datasets.length > 1 && <label className="material-dataset-picker">Property dataset<select aria-label="Property dataset" value={material.datasetId} onChange={e => setSelected(e.target.value)}>{datasets.map(d => <option key={d.datasetId} value={d.datasetId}>{d.dataset}</option>)}</select></label>}
    <div className="property-reference">
      <div><strong>{source.publisher}</strong><span>{source.date ? `Published / revised ${date(source.date)}` : `Accessed ${date(source.accessed)}`}</span></div>
      <a href={referenceUrl(source, source.page, { datasetId: material.datasetId })} target={source.kind === "book" ? undefined : "_blank"} rel="noreferrer">{source.kind === "book" ? "View source details" : "Open reference"} <ArrowUpRight size={13} /></a>
    </div>
    <p className="dataset-summary"><strong>{material.dataset}</strong><br />{material.conditions}{source.kind === "book" && <><br />Daniel &amp; Ishai, second edition · printed page {source.printedPage}. Select a property to review its citation and recorded source units.</>}</p>
    <PropertyTable key={material.datasetId} properties={material.properties.map(p => ({ ...p, value: propertyDisplayValue(p), context: `${p.basis} · ${p.direction}`, referenceUrl: referenceUrl(source, p.sourcePage, { datasetId: material.datasetId, propertyKey: p.key }) }))} />
    <p className="dataset-application">{material.application}</p>
    <details className="cited-reference-details">
      <summary>Reference &amp; test details</summary>
      <p><a href={referenceUrl(source, source.page, { datasetId: material.datasetId })} target={source.kind === "book" ? undefined : "_blank"} rel="noreferrer">{source.title} <ArrowUpRight size={13} /></a><br />{source.authors && <>{source.authors}<br /></>}{source.revision} · Accessed {date(source.accessed)}{source.kind === "book" && <><br /><a href={source.url} target="_blank" rel="noreferrer">Book information at the publisher <ArrowUpRight size={13} /></a></>}</p>
      {material.reviewedOn && <p>Library review: {date(material.reviewedOn)} · Record revision {material.recordRevision}. Publication dates remain those of the original reports.</p>}
      {material.recordDetails && <ul>{material.recordDetails.map(detail => <li key={detail}>{detail}</li>)}</ul>}
      {material.supportingReferences && <><h4>Supporting reports &amp; specifications</h4><ul>{material.supportingReferences.map(ref => <li key={ref.id}><a href={`${ref.url}#page=${ref.page}`} target="_blank" rel="noreferrer">{ref.title} <ArrowUpRight size={13} /></a><br />{ref.revision} · {ref.date && date(ref.date)}<br />{ref.role}</li>)}</ul></>}
      <ul>{material.properties.map(p => <li key={p.key}><strong>{p.label}</strong> · {p.method}<br />{p.conditions}<br /><a href={referenceUrl(source, p.sourcePage, { datasetId: material.datasetId, propertyKey: p.key })} target={source.kind === "book" ? undefined : "_blank"} rel="noreferrer">{p.printedPage ? `Printed page ${p.printedPage}` : `Page ${p.sourcePage}`} · {p.evidence}</a></li>)}</ul>
      <p className="reference-monitor-status">{source.kind === "book" ? "This record preserves the cited book edition. A new edition requires review before any values change." : changed ? "A changed document has been detected. The displayed values stay on this edition until the replacement is reviewed." : unavailable ? "Automatic update status is currently unavailable. The displayed reference remains pinned to the cited edition." : failed ? "The publisher could not be reached during the latest check. The cited dataset is retained." : overdue ? "An update check is overdue. The displayed values stay on the cited edition." : "Automatic source checks are active. Reviewed updates appear here; existing analysis exports keep their original dataset."}</p>
    </details>
    <div className="material-detail-footer"><button className="text-button" onClick={() => downloadFile(`${material.id}-${material.datasetId}.json`, JSON.stringify(exportCitedMaterial(material), null, 2), "application/json")}><ArrowDownToLine size={14} /> Export referenced values</button><Link className="button primary small" href={`/chat?material=${material.id}`}>Discuss this material <ArrowUpRight size={14} /></Link></div>
  </div>;
}
