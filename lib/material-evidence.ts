// References describe methods and source coverage. They never certify the classroom values.
export type StandardReference = {
  id: string; title: string; url: string; monitorId?: string;
};
export const standards: Record<string, StandardReference> = {
  D3039: { id: "D3039", title: "ASTM D3039/D3039M · tensile properties", url: "https://store.astm.org/d3039_d3039m-17r25.html", monitorId: "astm-d3039" },
  D6641: { id: "D6641", title: "ASTM D6641/D6641M · compression", url: "https://store.astm.org/d6641_d6641m-23.html", monitorId: "astm-d6641" },
  D5379: { id: "D5379", title: "ASTM D5379/D5379M · V-notched beam shear", url: "https://store.astm.org/d5379_d5379m-19r26.html", monitorId: "astm-d5379" },
  D5766: { id: "D5766", title: "ASTM D5766/D5766M · open-hole laminate tension", url: "https://store.astm.org/d5766_d5766m-23.html", monitorId: "astm-d5766" },
  C273: { id: "C273", title: "ASTM C273/C273M · core shear", url: "https://store.astm.org/c0273_c0273m-20.html", monitorId: "astm-c273" },
  C365: { id: "C365", title: "ASTM C365/C365M · core compression", url: "https://store.astm.org/c0365_c0365m-22.html", monitorId: "astm-c365" },
  D1621: { id: "D1621", title: "ASTM D1621 · rigid foam compression", url: "https://store.astm.org/standards/d1621", monitorId: "astm-d1621" },
  D1623: { id: "D1623", title: "ASTM D1623 · rigid foam tension", url: "https://store.astm.org/d1623-17r23.html", monitorId: "astm-d1623" },
  ISO845: { id: "ISO845", title: "ISO 845 · apparent density", url: "https://www.iso.org/standard/39408.html" },
  AMS401: { id: "AMS401", title: "SAE AMS-STD-401 · sandwich/core test methods", url: "https://saemobilus.sae.org/standards/amsstd401-sandwich-constructions-core-materials-general-test-methods" },
};
export type MaterialEvidence = {
  identity: "identified" | "confirmation-needed" | "identity-needed";
  sourceIds: string[];
  references: { title: string; url: string; relationship: string }[];
  methodIds: string[];
  issue: string;
};
const laminateMethods = ["D3039", "D6641", "D5379", "D5766"];
const hexcel = "https://www.hexcel.com/products/prepregs-resins/hexply-prepregs/";
const specifics: Record<string, MaterialEvidence> = {
  "as4-3501": { identity: "confirmation-needed", sourceIds: [], methodIds: laminateMethods,
    references: [{ title: "Hexcel · HexPly supplier catalog", url: hexcel, relationship: "Supplier investigation; current exact AS4/3501-6 datasheet not verified" }],
    issue: "Confirm the exact prepreg specification, fiber form, resin content and cure process with Hexcel. Do not substitute AS4/8552 properties." },
  agp370: { identity: "confirmation-needed", sourceIds: [], methodIds: laminateMethods,
    references: [{ title: "Hexcel · HexPly supplier catalog", url: hexcel, relationship: "Supplier investigation; exact AGP370-5H / 3501-6S identity unresolved" }],
    issue: "Confirm fabric designation, weave and resin suffix. Similar 3501-6 fabrics are not interchangeable property sources." },
  "eglass-3783": { identity: "identity-needed", sourceIds: [], methodIds: laminateMethods, references: [],
    issue: "Identify the manufacturer, reinforcement product, resin and cure. The class label does not establish an exact qualified material system." },
  "m10e-3783": { identity: "confirmation-needed", sourceIds: [], methodIds: laminateMethods,
    references: [{ title: "Hexcel · supplier catalog", url: hexcel, relationship: "Investigation lead only; M10E/3783 is not verified against an exact supplier record" }],
    issue: "The school table labels M10E as reinforcement and 3783 as resin. These designations require supplier confirmation; do not assign a different M9/M10 product by name similarity." },
  "7781-e765": { identity: "identified", sourceIds: ["park-e765-us"], methodIds: laminateMethods,
    references: [{ title: "Park Aerospace · E-765", url: "https://parkaerospace.com/aerospace-products/e-765/", relationship: "Manufacturer identifies 7781 E-glass/E-765; exact processing and allowable database require confirmation" }],
    issue: "Manufacturer typical values are not specification values. Obtain the applicable AGATE/qualification data and process equivalency before design use." },
  m55j: { identity: "identified", sourceIds: ["toray-ex1515"], methodIds: laminateMethods,
    references: [{ title: "Toray · M55J / EX-1515", url: "https://www.toraytac.com/product-explorer/products/T3GL/EX-1515", relationship: "Page 3 reports M55J 0° laminate properties at 60% fiber volume with autoclave cure. The school dataset describes vacuum-oven processing; do not merge the two." }],
    issue: "EX-1515 is cyanate ester. Use the dataset matching your process. The manufacturer's tensile-modulus SI and US columns disagree; that property remains flagged." },
  cf0302: { identity: "confirmation-needed", sourceIds: [], methodIds: laminateMethods,
    references: [{ title: "Syensqo · MTM 49-1L", url: "https://www.syensqo.com/en/product/mtm-49-1l", relationship: "Related family only; not verified as the class record's MTM49LT" }],
    issue: "Confirm CF0302 fabric and exact MTM49LT product with the supplier. MTM49-1L and MTM49-3 are not established replacements." },
  "nomex-aramid": { identity: "identified", sourceIds: ["hexcel-hrh10-us"], methodIds: ["AMS401", "C273", "C365"],
    references: [{ title: "Hexcel · HexWeb HRH-10", url: "https://www.hexcel.com/products/honeycomb/hexweb-honeycomb/", relationship: "Manufacturer datasheet; match HRH-10, 1/8 inch cells, 1.8 lb/ft³ and test thickness" }],
    issue: "Keep L/W shear directions, typical/minimum basis and 0.500 inch test thickness distinct. Supplier sheet cites AMS-STD-401, not a demonstrated latest-edition test." },
  "aluminum-core": { identity: "confirmation-needed", sourceIds: ["hexcel-criii"], methodIds: ["AMS401", "C273", "C365"],
    references: [{ title: "Hexcel · HexWeb CR III", url: "https://www.hexcel.com/products/honeycomb/hexweb-honeycomb/", relationship: "Candidate manufacturer source; original class table incorrectly labels the aluminum column Nomex" }],
    issue: "Confirm supplier, 5052 alloy, cell size, foil gauge, density, finish and thickness. Candidate source coverage does not resolve the original brand error." },
  "divinycell-h45": { identity: "identified", sourceIds: ["diab-divinycell-h-si"], methodIds: ["D1621", "D1623", "C273", "ISO845"],
    references: [{ title: "Diab · Divinycell H", url: "https://diabgroup.com/products-services/divinycell-pvc/divinycell-h/", relationship: "Exact H45 grade in the manufacturer series datasheet" }],
    issue: "Separate nominal and minimum values. Record temperature, direction and processing limits; supplier minimum values are not statistical A/B allowables." },
  "divinycell-h250": { identity: "identified", sourceIds: ["diab-divinycell-h-si"], methodIds: ["D1621", "D1623", "C273", "ISO845"],
    references: [{ title: "Diab · Divinycell H", url: "https://diabgroup.com/products-services/divinycell-pvc/divinycell-h/", relationship: "Exact H250 grade in the manufacturer series datasheet" }],
    issue: "Separate nominal and minimum values. Record temperature, direction and processing limits; supplier minimum values are not statistical A/B allowables." },
  baltek: { identity: "identity-needed", sourceIds: ["baltek-sbc"], methodIds: ["C273", "C365"],
    references: [{ title: "3A Composites · BALTEK SBC", url: "https://www.3accorematerials.com/en/markets-and-products/baltek-balsa/baltek-sbc-balsa", relationship: "Candidate family only; the original 8 lb/ft³ record does not establish an SBC grade" }],
    issue: "Confirm SB/SBC product series, grade, density band and finishing. Do not infer SBC.80 solely from nominal density." },
};
const genericIds = ["carbon-ud-nominal", "carbon-ud-wet", "carbon-weave-nominal", "carbon-weave-wet", "carbon-weave-vartm", "glass-ud-nominal", "glass-ud-wet", "glass-weave-nominal", "glass-weave-wet", "glass-weave-vartm"];
export const materialEvidence: Record<string, MaterialEvidence> = { ...specifics };
for (const id of genericIds) materialEvidence[id] = {
  identity: "identity-needed", sourceIds: [], references: [], methodIds: laminateMethods,
  issue: "Supplier and fiber/fabric part number, resin/hardener system, cure schedule and fiber volume are missing. Retained as a classroom reference; exact product data cannot be assigned yet.",
};

export type PropertyValue = {
  key: string; label: string; value: number; unit: string;
  basis: "nominal" | "minimum"; method: string; conditions: string; direction: string;
  sourcePage: number; evidence: string; review?: string;
};
export type SourceStatus = {
  id: string; name: string; kind: "datasheet" | "standard-metadata" | "reference-document";
  sourceUrl: string; documentUrl: string | null; fingerprint: string | null;
  revision: string | null; revisionDate: string | null; datePrecision: "day" | "month" | null;
  dateMeaning: string; lastChecked: string | null; lastSuccess: string | null; nextCheck: string;
  outcome: string; failed: boolean; review: "accepted" | "rejected" | "pending" | "not-captured";
  propertyExtraction: "not-configured" | "not-captured" | "ready-for-review" | "review-required";
};
export type MaterialFeed = {
  schemaVersion: 1; generatedAt: string;
  sources: SourceStatus[];
  candidates: { materialId: string; sourceId: string; fingerprint: string; properties: PropertyValue[]; status: "unreviewed" }[];
  releases: { materialId: string; sourceId: string; fingerprint: string; releaseId: string; approvedAt: string; sourceRevision: string | null; sourceRevisionDate: string | null; documentUrl: string; properties: PropertyValue[]; use: "reference-only" }[];
};
export function engineeringEligibility(materialId: string) {
  if (!materialEvidence[materialId]) throw new Error("Unknown material");
  return { scope: "qualified-design-allowables", eligible: false as const, reason: "No qualified design release exists. Use analysisPacket for explicitly scoped preliminary inputs; reference lookup remains available." };
}
export function requireEngineeringProperties(materialId: string): never {
  throw new Error(engineeringEligibility(materialId).reason);
}
