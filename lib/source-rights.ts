// Every source the library cites carries a rights class that says what the website may
// do with it. The policy below is the single place that decides what is shown (ADR-0018).
// The evidence for each source's class is a review record and lives in lib/source-provenance.ts.
import { textbookSource } from "./textbook-source";

export type SourceRights = "public-domain" | "open-publisher" | "licensed-reference" | "user-supplied";

export type RightsPolicy = {
  label: string;
  // What the public website may show for sources in this class.
  showValues: boolean;      // recorded property values with their citation
  copyDocument: boolean;    // host a copy of the document, scans or extracted text
  linkDocument: boolean;    // link to the publisher's own copy of the document
  publicRecord: boolean;    // the dataset may appear in the public library at all
  summary: string;          // what the class means, for the references list
  note: string;             // one line beside a dataset's rights chip
};

export const sourceRightsPolicy: Record<SourceRights, RightsPolicy> = {
  "public-domain": {
    label: "Public domain",
    showValues: true, copyDocument: true, linkDocument: true, publicRecord: true,
    summary: "Free of copyright, for example a US government handbook. We show its values with their page and link the official copy.",
    note: "Free of copyright. Values are shown with their page; the official copy is linked.",
  },
  "open-publisher": {
    label: "Open publisher data",
    showValues: true, copyDocument: false, linkDocument: true, publicRecord: true,
    summary: "Published openly by its owner, for example NCAMP and NASA reports or a manufacturer's datasheet. We show the values with their page and link the publisher's copy.",
    note: "Published openly by its owner. Values are shown with their page; the publisher's copy is linked.",
  },
  "licensed-reference": {
    label: "Licensed reference",
    showValues: true, copyDocument: false, linkDocument: false, publicRecord: true,
    summary: "A copyrighted work, or one whose terms are not confirmed, for example a textbook or CMH-17. We show only individual values with their table or figure and page; consult your own copy.",
    note: "Values are cited by table or figure and page; consult your own copy.",
  },
  "user-supplied": {
    label: "User supplied",
    showValues: false, copyDocument: false, linkDocument: false, publicRecord: false,
    summary: "Data a user supplies. Never shown on public pages.",
    note: "Never shown on public pages.",
  },
};

export const sourceRightsClasses = Object.keys(sourceRightsPolicy) as SourceRights[];

export function rightsPolicy(rights: SourceRights): RightsPolicy {
  const policy = sourceRightsPolicy[rights];
  if (!policy) throw new Error(`Unknown source rights class: ${rights}`);
  return policy;
}

// Handbooks the library relies on. MIL-HDBK-17-2F also backs two historical records.
export const handbookReferences = [
  { id: "mil-hdbk-17-2f", title: "MIL-HDBK-17-2F · Composite Materials Handbook, Volume 2: Polymer Matrix Composites, Materials Properties (2002; canceled 2013, superseded by CMH-17)",
    publisher: "US Department of Defense", rights: "public-domain" as const,
    url: "https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=53882" },
  { id: "cmh-17-2g", title: "CMH-17 Rev. G · Composite Materials Handbook, Volume 2 (SAE International, 2012)",
    publisher: "CMH-17 at Wichita State University; published by SAE International", rights: "licensed-reference" as const,
    url: "https://saemobilus.sae.org/content/R-423" },
  { id: "daniel-ishai-2006", title: textbookSource.fullCitation,
    publisher: "Oxford University Press", rights: "licensed-reference" as const,
    url: textbookSource.url },
];

/** The test standards a coupon may follow (ADR-0072): licensed references under ADR-0018 amendment 1. The fea package holds individual values
 * from them, each with its clause and in our words, and judges a specimen against them; their text, tables, figures and PDFs are never in
 * this repository. Every standard the form definition offers must be listed here (tests/source-rights.test.ts). */
export const testStandardReferences = [
  { designation: "ASTM D3039/D3039M-17", title: "Standard Test Method for Tensile Properties of Polymer Matrix Composite Materials",
    publisher: "ASTM International", rights: "licensed-reference" as const,
    url: "https://store.astm.org/d3039_d3039m-17r25.html" },
  { designation: "ASTM D638-22", title: "Standard Test Method for Tensile Properties of Plastics",
    publisher: "ASTM International", rights: "licensed-reference" as const,
    url: "https://store.astm.org/d0638-22.html" },
  { designation: "ASTM C1869-18(2023)", title: "Standard Test Method for Open-Hole Tensile Strength of Fiber-Reinforced Advanced Ceramic Composites",
    publisher: "ASTM International", rights: "licensed-reference" as const,
    url: "https://store.astm.org/c1869-18.html" },
  { designation: "ASTM D4018-23", title: "Standard Test Methods for Properties of Continuous Filament Carbon and Graphite Fiber Tows",
    publisher: "ASTM International", rights: "licensed-reference" as const,
    url: "https://store.astm.org/d4018-23.html" },
];
