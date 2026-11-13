/**
 * How every source the library cites was checked: the fingerprint of the copy that was read, the check itself and the evidence for
 * its rights class (ADR-0018 amendment 2). These are review records, not customer copy, so they live here and in
 * `source-provenance.json`, apart from the records the pages read (`curated-materials.ts`, `textbook-source.ts`,
 * `qualification-references.json`, `source-rights.ts`). Only scripts, tests and the revision monitor (`services/material-monitor`)
 * import this module; no page may: `tests/source-provenance.test.ts` walks every import reachable from `app/` and `components/`
 * and fails if one reaches it.
 */
import recorded from "./source-provenance.json";
import publishedReferences from "./published-material-references.json";

export type SourceProvenance = { sha256: string | null; verification: string; rightsEvidence: string };

const manufacturerDatasheet = {
  verification: "Exact grade, units, conditions and table cells checked against manufacturer document. Conflicting rows omitted.",
  rightsEvidence: "Manufacturer datasheet published on the manufacturer's website. Linked, not copied.",
};

/** Every cited source by its id. A manufacturer datasheet's fingerprint is the one its reviewed release records. */
export const sourceProvenance: Record<string, SourceProvenance> = {
  ...(recorded as Record<string, SourceProvenance>),
  ...Object.fromEntries(publishedReferences.map(r => [r.sourceId, { sha256: r.fingerprint, ...manufacturerDatasheet }])),
};

export function provenanceOf(id: string): SourceProvenance {
  const entry = sourceProvenance[id];
  if (!entry) throw new Error(`No provenance is recorded for source ${id}`);
  return entry;
}

/** Rights evidence for the handbooks `source-rights.ts` names, by id. */
export const handbookRightsEvidence: Record<string, string> = {
  "mil-hdbk-17-2f": "Cover carries Distribution Statement A, approved for public release, distribution unlimited; issued as a DoD handbook (17 U.S.C. § 105). Canceled 26 March 2013 per ASSIST; historical data only.",
  "cmh-17-2g": "Copyrighted; sold by SAE. Section-level citations only. No handbook content is reproduced; readers consult their own copy.",
  "daniel-ishai-2006": "Copyrighted textbook; no redistribution permission recorded (ADR-0010). Individual values cited by table and printed page.",
};

/** Rights evidence for the test standards a coupon may follow (ADR-0072), by designation. The edition only; the standards are
 * licensed references whose values are held with their clause, in our words. */
export const testStandardRightsEvidence: Record<string, string> = {
  "ASTM D3039/D3039M-17": "Copyrighted and sold by ASTM. Individual values with their clause only, in our words; consult your own copy. "
    + "The publisher lists D3039/D3039M-17(2025), a reapproval, as active.",
  "ASTM D638-22": "Copyrighted and sold by ASTM; D638-22 is the active edition. Individual values with their clause only, in our words; "
    + "consult your own copy (ADR-0075).",
  "ASTM C1869-18(2023)": "Copyrighted and sold by ASTM. Individual values with their clause only, in our words; consult your own copy.",
  "ASTM D4018-23": "Copyrighted and sold by ASTM. Individual values with their clause only, in our words; consult your own copy. "
    + "No finite element model: the engine reduces a test record (ADR-0074).",
};
