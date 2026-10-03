"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowUpRight } from "lucide-react";
import { textbookMaterials } from "@/lib/textbook-materials";
import { textbookPages, textbookSource } from "@/lib/textbook-source";
import { dualUnits, propertyDisplayValue, propertyName } from "@/lib/property-units";
import { referenceUrl } from "@/lib/curated-materials";

export function SourceViewer() {
  const params = useSearchParams();
  const page = textbookPages.find(p => String(p.pdfPage) === params.get("page"));
  const datasetId = params.get("dataset");
  const propertyKey = params.get("property");
  const material = textbookMaterials.find(m => m.datasetId === datasetId);
  const property = material?.properties.find(p => p.key === propertyKey);
  const valid = params.get("source") === textbookSource.id && page
    && (!datasetId || material) && (!propertyKey || property)
    && (!material || material.properties.some(p => p.sourcePage === page.pdfPage))
    && (!property || property.sourcePage === page.pdfPage);

  if (!valid || !page) return <section className="section source-empty">
    <span className="eyebrow">SOURCE REFERENCE</span>
    <h1>Source reference not available</h1>
    <p>This link does not identify an available source page and matching property. Select a property in the material library to open its reference.</p>
    <Link className="text-button" href="/library"><ArrowLeft size={16} /> Return to material library</Link>
  </section>;

  const display = property && dualUnits(propertyDisplayValue(property), property.unit);
  const sourceValue = property?.sourceValue ?? property?.value;
  const sourceUnit = property?.sourceUnit ?? property?.unit;
  return <section className="section source-content">
    <Link className="source-back" href="/library"><ArrowLeft size={15} /> Material library</Link>
    <div className="source-heading">
      <div><span className="eyebrow">SOURCE REFERENCE</span><h1>{property ? propertyName(property.label) : `Table ${page.table}`}</h1>
        <p>{material?.name || page.title}{property && <> · {property.symbol || property.key} · {property.direction}</>}</p>
      </div>
      <div className="source-location"><strong>Table {page.table}</strong><span>Printed page {page.printedPage}</span><span>PDF page {page.pdfPage}</span></div>
    </div>
    {property && display && <div className="source-values" aria-label="Source value and website conversions">
      <div><span>Recorded source value</span><strong>{sourceValue} {sourceUnit === "—" ? "(dimensionless)" : sourceUnit}</strong><small>{material!.name} column</small></div>
      <div><span>Website · SI / metric</span><strong>{display.si}</strong><small>Converted from the source value where needed</small></div>
      <div><span>Website · English / imperial</span><strong>{display.english}</strong><small>Calculated conversion; printed rounding may differ</small></div>
    </div>}
    <p className="source-reading-guide">{property ? `${property.evidence}. ` : ""}Values above preserve the recorded source units. Website conversions can differ from the book’s separately rounded imperial entries.</p>
    <div className="source-document-note">
      <strong>Consult the cited table in your copy</strong>
      <p>Table {page.table}, printed page {page.printedPage}, in the second edition of <em>{textbookSource.title}</em>. Page scans are not distributed here.</p>
      <a href={textbookSource.url} target="_blank" rel="noreferrer">Find the book at the publisher <ArrowUpRight size={14} /></a>
    </div>
    <div className="source-attribution">
      <div><strong>{textbookSource.title}</strong><p>{textbookSource.authors} · Second edition · {textbookSource.publisher}, {textbookSource.date}.<br />{material?.conditions}</p></div>
      <a href={textbookSource.url} target="_blank" rel="noreferrer">Book information <ArrowUpRight size={14} /></a>
    </div>
    <nav className="source-page-links" aria-label="Available textbook tables">
      <span>Other cited pages</span>
      {textbookPages.map(p => <Link key={p.pdfPage} href={referenceUrl({ ...textbookSource, page: p.pdfPage }, p.pdfPage)} aria-current={p.pdfPage === page.pdfPage ? "page" : undefined}>Table {p.table} · p. {p.printedPage}</Link>)}
    </nav>
  </section>;
}
