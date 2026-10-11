// Every source the library cites carries a rights class that says what the website may
// do with it. The policy below is the single place that decides what is shown (ADR-0018).
export type SourceRights = "public-domain" | "open-publisher" | "licensed-reference" | "user-supplied";

export type RightsPolicy = {
  label: string;
  // What the public website may show for sources in this class.
  showValues: boolean;      // recorded property values with their citation
  copyDocument: boolean;    // host a copy of the document, scans or extracted text
  linkDocument: boolean;    // link to the publisher's own copy of the document
  publicRecord: boolean;    // the dataset may appear in the public library at all
  summary: string;
};

export const sourceRightsPolicy: Record<SourceRights, RightsPolicy> = {
  "public-domain": {
    label: "Public domain",
    showValues: true, copyDocument: true, linkDocument: true, publicRecord: true,
    summary: "Free of copyright, for example a US government work. Values, tables and quoted text may be shown and a copy may be hosted.",
  },
  "open-publisher": {
    label: "Open publisher data",
    showValues: true, copyDocument: false, linkDocument: true, publicRecord: true,
    summary: "The publisher distributes the document publicly, for example NCAMP reports, NASA reports and manufacturer datasheets. Values are shown with their citation and a link to the publisher's copy. No copy is hosted here.",
  },
  "licensed-reference": {
    label: "Licensed reference",
    showValues: true, copyDocument: false, linkDocument: false, publicRecord: true,
    summary: "A copyrighted work we hold a copy of without redistribution rights, for example a textbook or CMH-17. Only the individual recorded values used by this library are shown, with the exact table and page, and readers are directed to their own copy. No scans, extracted text, tables or PDFs are published.",
  },
  "user-supplied": {
    label: "User supplied",
    showValues: false, copyDocument: false, linkDocument: false, publicRecord: false,
    summary: "Data a user uploads, such as internal allowables or their own licensed handbook extracts. Visible only in that user's private workspace and never published.",
  },
};

export const sourceRightsClasses = Object.keys(sourceRightsPolicy) as SourceRights[];

export function rightsPolicy(rights: SourceRights): RightsPolicy {
  const policy = sourceRightsPolicy[rights];
  if (!policy) throw new Error(`Unknown source rights class: ${rights}`);
  return policy;
}

// Handbooks the library names on its references panel. MIL-HDBK-17-2F also backs two historical records.
export const handbookReferences = [
  { id: "mil-hdbk-17-2f", title: "MIL-HDBK-17-2F · Composite Materials Handbook, Volume 2: Polymer Matrix Composites, Materials Properties (2002; canceled 2013, superseded by CMH-17)",
    publisher: "US Department of Defense", rights: "public-domain" as const,
    rightsEvidence: "Cover carries Distribution Statement A, approved for public release, distribution unlimited; issued as a DoD handbook (17 U.S.C. § 105). Canceled 26 March 2013 per ASSIST; historical data only.",
    url: "https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=53882" },
  { id: "cmh-17-2g", title: "CMH-17 Rev. G · Composite Materials Handbook, Volume 2 (SAE International, 2012)",
    publisher: "CMH-17 at Wichita State University; published by SAE International", rights: "licensed-reference" as const,
    rightsEvidence: "Copyrighted; sold by SAE. Section-level citations only. No handbook content is reproduced; readers consult their own copy.",
    url: "https://saemobilus.sae.org/content/R-423" },
  { id: "daniel-ishai-2006", title: "Daniel and Ishai · Engineering Mechanics of Composite Materials, second edition (Oxford University Press, 2006)",
    publisher: "Oxford University Press", rights: "licensed-reference" as const,
    rightsEvidence: "Copyrighted textbook; no redistribution permission recorded (ADR-0010). Individual values cited by table and printed page.",
    url: "https://global.oup.com/academic/product/engineering-mechanics-of-composite-materials-9780195150971" },
];
