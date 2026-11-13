"use client";
import { ArrowDownToLine, ArrowRight, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { couponWorkspaceMaterialIds, exportCitedMaterial, exportFileName, materialDatasets, referenceUrl, type CitedMaterial, type CitedProperty } from "@/lib/curated-materials";
import type { MaterialFeed } from "@/lib/material-evidence";
import { downloadFile } from "@/lib/demo";
import { propertyDisplayValue } from "@/lib/property-units";
import { rightsPolicy } from "@/lib/source-rights";
import { textbookSource } from "@/lib/textbook-source";
import { materialMonitorEnabled } from "./material-provenance";
import { PropertyTable } from "./property-table";

function date(value: string) {
  if (/^\d{4}$/.test(value)) return value;
  const month = /^\d{4}-\d{2}$/.test(value);
  return new Date(`${value}${month ? "-01" : ""}T12:00:00Z`).toLocaleDateString("en-US", month ? { month: "long", year: "numeric", timeZone: "UTC" } : { dateStyle: "medium", timeZone: "UTC" });
}

/** The basis most rows share. It is stated once above the table; a row with another basis says so beside its direction.
 * When no basis covers more than half the rows, every row states its own. */
function commonBasis(properties: CitedProperty[]) {
  const counts = new Map<string, number>();
  for (const p of properties) counts.set(p.basis, (counts.get(p.basis) ?? 0) + 1);
  const [basis, count] = [...counts].sort((a, b) => b[1] - a[1])[0] ?? ["", 0];
  return count > properties.length / 2 ? basis : "";
}

/** True when the dataset's label already names the basis, e.g. "NCAMP 2019 · measured means" and "Measured mean": the
 * summary then states it once, in the label. */
function labelNamesBasis(dataset: string, basis: string) {
  const named = dataset.split(" · ").slice(1).join(" ").toLowerCase().split(/\s+/)[0];
  return !!named && named === basis.toLowerCase().split(/[\s,]+/)[0];
}

const list = (items: (string | number)[]) => items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;

/** Where a book dataset's rows come from, e.g. "Tables A.4 and A.6, printed pp. 377 and 380". */
function bookLocation(properties: CitedProperty[]) {
  const tables = [...new Set(properties.map(p => p.evidence.match(/^Table ([^,]+)/)?.[1]).filter((t): t is string => !!t))];
  const pages = [...new Set(properties.map(p => p.printedPage).filter((n): n is number => n !== undefined))].sort((a, b) => a - b);
  return `${tables.length > 1 ? "Tables" : "Table"} ${list(tables)}, printed ${pages.length > 1 ? "pp." : "p."} ${list(pages)}`;
}

/** A citation link: inside the site it opens in place; outside it opens a new tab and says so. */
function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  if (href.startsWith("/")) return <Link href={href}>{children} <ArrowRight size={13} /></Link>;
  return <a href={href} target="_blank" rel="noreferrer">{children} <ArrowUpRight size={13} /><span className="sr-only"> (opens in a new tab)</span></a>;
}

function linkLabel(source: CitedMaterial["source"]) {
  if (source.kind === "book") return "View source details";
  if (source.linkKind === "search") return `Search ${new URL(source.url).hostname.replace(/^www\./, "")}`;
  return "Open reference";
}

export function CitedMaterialProperties({ material: initial, feed, stale }: { material: CitedMaterial; feed: MaterialFeed | null; stale: boolean }) {
  const datasets = materialDatasets(initial);
  const [selected, setSelected] = useState(initial.datasetId);
  const material = datasets.find(d => d.datasetId === selected) || initial;
  const { source } = material;
  const book = source.kind === "book";
  // A search link is labelled once, beside the publisher; the property names and citation lines are then plain text.
  const search = source.linkKind === "search";
  const references = [source, ...(material.supportingReferences || [])];
  const observations = references.map(ref => feed?.sources.find(s => s.id === ref.id));
  // The latest check compares only with the check before it; the monitor also says whether the document differs from the
  // reviewed copy, so a change stays reported until it is reviewed.
  const changed = observations.some(o => o?.changedSinceReview || o?.outcome === "changed");
  const unavailable = stale || observations.some(o => !o?.lastSuccess);
  const failed = observations.some(o => o?.failed);
  const overdue = observations.some(o => o && Date.now() > Date.parse(o.nextCheck));
  const status = !materialMonitorEnabled ? "Values are pinned to the cited edition."
    : book ? "This record preserves the cited book edition. A new edition requires review before any values change."
    : changed ? "A changed document has been detected. The displayed values stay on this edition until the replacement is reviewed."
    : unavailable ? "Automatic update status is currently unavailable. The displayed reference remains pinned to the cited edition."
    : failed ? "The publisher could not be reached during the latest check. The cited dataset is retained."
    : overdue ? "An update check is overdue. The displayed values stay on the cited edition."
    : "Automatic source checks are active. Reviewed updates appear here; existing analysis exports keep their original dataset.";
  const rights = rightsPolicy(source.rights);
  const basis = commonBasis(material.properties);
  const sourceHref = referenceUrl(source, source.page, { datasetId: material.datasetId });
  const propertyHref = (p: CitedProperty) => search ? undefined : referenceUrl(source, p.sourcePage, { datasetId: material.datasetId, propertyKey: p.key });
  return <div className="material-properties cited-properties">
    {datasets.length > 1 && <label className="material-dataset-picker">Property dataset<select aria-label="Property dataset" value={material.datasetId} onChange={e => setSelected(e.target.value)}>{datasets.map(d => <option key={d.datasetId} value={d.datasetId}>{d.dataset}</option>)}</select></label>}
    <div className="property-reference">
      <div><strong>{source.publisher}</strong><span>{source.date ? `Published ${date(source.date)}` : `Accessed ${date(source.accessed)}`}</span></div>
      <SourceLink href={sourceHref}>{linkLabel(source)}</SourceLink>
    </div>
    <p className="source-rights"><span className={`rights-chip rights-${source.rights}`}>{rights.label}</span><span>{rights.note}</span></p>
    <p className="dataset-summary"><strong>{material.dataset}</strong><br />{material.conditions}
      {basis && !labelNamesBasis(material.dataset, basis) && <><br />Basis: {basis.charAt(0).toLowerCase() + basis.slice(1)}.</>}
      {book && <><br />{textbookSource.shortCitation}, {bookLocation(material.properties)}. Select a property name to see its citation.</>}</p>
    {rights.showValues
      ? <PropertyTable key={material.datasetId} caption={`${material.name} properties · ${material.dataset}`} properties={material.properties.map(p => ({ ...p, value: propertyDisplayValue(p),
        context: [p.direction === "Bulk" ? "" : p.direction, p.basis === basis ? "" : p.basis].filter(Boolean).join(" · "),
        referenceUrl: propertyHref(p) }))} />
      : <p className="dataset-summary">Values from this source are not published. Consult {source.title}, printed page {source.printedPage ?? source.page}, in your own copy.</p>}
    <p className="dataset-application">{material.application}</p>
    <details className="cited-reference-details">
      <summary>Reference &amp; test details</summary>
      <p>{search ? source.title : <SourceLink href={sourceHref}>{source.title}</SourceLink>}<br />{source.authors && <>{source.authors}<br /></>}{source.revision}{!book && <> · Accessed {date(source.accessed)}</>}{book && <><br /><SourceLink href={source.url}>Book information at the publisher</SourceLink></>}</p>
      {material.reviewedOn && <p>Reviewed {date(material.reviewedOn)}</p>}
      {material.recordDetails && material.recordDetails.length > 0 && <ul>{material.recordDetails.map(detail => <li key={detail}>{detail}</li>)}</ul>}
      {material.supportingReferences && <><h4>Supporting reports &amp; specifications</h4><ul>{material.supportingReferences.map(ref => <li key={ref.id}><SourceLink href={referenceUrl(ref, ref.page)}>{ref.title}</SourceLink><br />{ref.revision} · {ref.date && date(ref.date)}<br />{ref.role}</li>)}</ul></>}
      <ul>{material.properties.map(p => { const citation = `${p.printedPage ? `Printed page ${p.printedPage}` : `Page ${p.sourcePage}`} · ${p.evidence}`; const href = propertyHref(p);
        return <li key={p.key}><strong>{p.label}</strong> · {p.method}<br />{p.conditions}<br />{href ? <SourceLink href={href}>{citation}</SourceLink> : citation}</li>; })}</ul>
      <p className="reference-monitor-status">{status}</p>
    </details>
    <div className="material-detail-footer">
      <button className="text-button" onClick={() => downloadFile(exportFileName(material), JSON.stringify(exportCitedMaterial(material), null, 2), "application/json")}><ArrowDownToLine size={14} /> Export referenced values</button>
      {couponWorkspaceMaterialIds.has(material.id) && <Link className="button primary small" href={`/workspace/fea?material=${material.id}`}>Analyse in Workspace <ArrowRight size={14} /></Link>}
    </div>
  </div>;
}
