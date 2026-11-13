"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowUpRight } from "lucide-react";
import { textbookMaterials } from "@/lib/textbook-materials";
import { textbookPages, textbookSource } from "@/lib/textbook-source";
import { dualUnits, englishStressUnit, printedValue, propertyDisplayValue, propertyName } from "@/lib/property-units";
import { referenceUrl } from "@/lib/curated-materials";

// A reference link names the book's printed page (page=377), the page a reader can find in their own copy. Links made before
// that named the PDF page (page=397, in downloads already saved); they still open the same table, which shows its printed page.
// The two ranges do not overlap.
export function SourceViewer() {
  const params = useSearchParams();
  const requested = params.get("page");
  const page = textbookPages.find(p => String(p.printedPage) === requested) ?? textbookPages.find(p => String(p.pdfPage) === requested);
  const datasetId = params.get("dataset");
  const propertyKey = params.get("property");
  const material = textbookMaterials.find(m => m.datasetId === datasetId);
  const property = material?.properties.find(p => p.key === propertyKey);
  const valid = params.get("source") === textbookSource.id && page
    && (!datasetId || material) && (!propertyKey || property)
    && (!material || material.properties.some(p => p.printedPage === page.printedPage))
    && (!property || property.printedPage === page.printedPage);

  if (!valid || !page) return <section className="section source-empty">
    <span className="eyebrow">SOURCE REFERENCE</span>
    <h1>Reference not found</h1>
    <p>This reference link is not valid. Open a property in the Materials library to see its source.</p>
    <Link className="text-button" href="/library"><ArrowLeft size={16} /> Back to Materials library</Link>
  </section>;

  // The same stress unit as the material's table in the library.
  const stressUnit = material && englishStressUnit(material.properties.map(p => ({ value: propertyDisplayValue(p), unit: p.unit })));
  const display = property && dualUnits(propertyDisplayValue(property), property.unit, { stressUnit });
  const sourceValue = property?.sourceValue ?? property?.value;
  const sourceUnit = property?.sourceUnit ?? property?.unit;
  return <section className="section source-content">
    <Link className="source-back" href="/library"><ArrowLeft size={15} /> Materials library</Link>
    <div className="source-heading">
      <div><span className="eyebrow">SOURCE REFERENCE</span><h1>{property ? propertyName(property.label) : `Table ${page.table}`}</h1>
        <p>{material?.name || page.title}{property && <> · {[property.symbol, property.direction].filter(Boolean).join(" · ")}</>}</p>
      </div>
      <div className="source-location"><strong>Table {page.table}</strong><span>Printed page {page.printedPage}</span></div>
    </div>
    {property && display && <div className="source-values" aria-label="Value as printed and converted">
      <div><span>As printed</span><strong>{printedValue(sourceValue!, sourceUnit)}</strong><small>{material!.name} column</small></div>
      <div><span>SI / metric</span><strong>{display.si}</strong></div>
      <div><span>English / imperial</span><strong>{display.english}</strong></div>
    </div>}
    <p className="source-reading-guide">{property ? `${property.evidence}. ` : ""}Converted values are calculated from the printed value; the book rounds its own imperial entries separately.</p>
    <div className="source-document-note">
      <strong>Consult the cited table in your copy</strong>
      <p>Table {page.table}, printed page {page.printedPage}, in the second edition of <em>{textbookSource.title}</em>.</p>
      <p className="source-rights"><span className="rights-chip rights-licensed-reference">Licensed reference</span><span>{textbookSource.rightsNote}</span></p>
      <a href={textbookSource.url} target="_blank" rel="noreferrer">Book at the publisher <ArrowUpRight size={14} /><span className="sr-only"> (opens in a new tab)</span></a>
    </div>
    <div className="source-attribution">
      <div><p>{textbookSource.fullCitation}.{material?.conditions && <><br />{material.conditions}</>}</p></div>
    </div>
    <nav className="source-page-links" aria-label="Available textbook tables">
      <span>Other cited pages</span>
      {textbookPages.map(p => <Link key={p.printedPage} href={referenceUrl({ ...textbookSource, page: p.pdfPage }, p.pdfPage)} aria-current={p.printedPage === page.printedPage ? "page" : undefined}>Table {p.table} · p. {p.printedPage}</Link>)}
    </nav>
  </section>;
}
