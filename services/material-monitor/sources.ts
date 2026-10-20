import { standards, materialEvidence } from "../../lib/material-evidence";
import qualificationReferences from "../../lib/qualification-references.json";
export type Source = {
  id: string;
  name: string;
  publisher: string;
  materials: { id: string; name: string }[];
  pageUrl: string;
  hosts: string[];
  documentPattern: RegExp;
  identity: RegExp[];
  intervalHours: number;
  kind?: "standard-metadata" | "reference-document";
  standardCode?: string;
  maxDocumentBytes?: number;
};

// Curated publisher adapters. Adding a source requires code review, not a user-supplied URL.
// These are product datasheets, not statistical design allowables or testing standards.
export const sources: Source[] = [
  {
    id: "diab-divinycell-h-si",
    name: "Divinycell H · SI datasheet",
    publisher: "Diab",
    materials: [
      { id: "divinycell-h45", name: "Divinycell H45" },
      { id: "divinycell-h250", name: "Divinycell H250" },
    ],
    pageUrl: "https://diabgroup.com/products-services/divinycell-pvc/divinycell-h/",
    hosts: ["diabgroup.com", "www.diabgroup.com", "diab-media.azureedge.net"],
    documentPattern: /\/diab-divinycell-h-[^/?]*-si\.pdf$/i,
    identity: [/DIVINYCELL\s+H/i, /H\s*45\b/i, /H\s*250\b/i],
    intervalHours: 24,
  },
  {
    id: "hexcel-hrh10-us",
    name: "HexWeb HRH-10 · US datasheet",
    publisher: "Hexcel",
    materials: [{ id: "nomex-aramid", name: "HRH10-1/8-1.8 · grade match requires review" }],
    pageUrl: "https://www.hexcel.com/products/honeycomb/hexweb-honeycomb/",
    hosts: ["www.hexcel.com", "hexcel.com"],
    documentPattern: /\/HexWeb_HRH10_DataSheet_us[^/?]*\.pdf$/i,
    identity: [/HRH[\s-]*10/i, /HEXCEL/i],
    intervalHours: 24,
  },
];

sources.push(
  { id: "hexcel-criii", name: "HexWeb CR III · candidate family", publisher: "Hexcel",
    materials: [{ id: "aluminum-core", name: "Aluminum core · supplier/grade confirmation needed" }],
    pageUrl: "https://www.hexcel.com/products/honeycomb/hexweb-honeycomb/", hosts: ["www.hexcel.com", "hexcel.com"],
    documentPattern: /\/HexWeb_CRIII_DataSheet[^/?]*\.pdf$/i, identity: [/CR\s*III/i, /5052/], intervalHours: 24 },
  { id: "baltek-sbc", name: "BALTEK SBC · candidate family", publisher: "3A Composites",
    materials: [{ id: "baltek", name: "BALTEK balsa · exact grade needed" }],
    pageUrl: "https://www.3accorematerials.com/en/markets-and-products/baltek-balsa/baltek-sbc-balsa",
    hosts: ["www.3accorematerials.com", "3accorematerials.com"], documentPattern: /\/TDS-BALTEK-SBC-E-[^/?]+\.pdf$/i,
    identity: [/BALTEK/i, /SBC/i], intervalHours: 24 },
  { id: "toray-ex1515", name: "Toray EX-1515 · resin system", publisher: "Toray Advanced Composites",
    materials: [{ id: "m55j", name: "M55J / EX-1515 · reinforcement match needed" }],
    pageUrl: "https://www.toraytac.com/product-explorer/products/T3GL/EX-1515", hosts: ["www.toraytac.com", "toraytac.com"],
    documentPattern: /\/EX-1515_Cyanate-Ester_PDS\.pdf$/i, identity: [/EX[\s-]*1515/i, /cyanate/i], intervalHours: 24 },
  { id: "park-e765-us", name: "Park E-765 · US datasheet", publisher: "Park Aerospace",
    materials: [{ id: "7781-e765", name: "7781 / E-765" }],
    pageUrl: "https://parkaerospace.com/aerospace-products/e-765/", hosts: ["parkaerospace.com", "www.parkaerospace.com"],
    documentPattern: /\/E-765_US[^/?]*\.pdf$/i, identity: [/E[\s-]*765/i, /7781/], intervalHours: 24 },
);

// Fixed original publications: detect replacement bytes without pretending that a
// fresh download supplies newly qualified properties. Long/scanned reports are
// not passed through the short-datasheet numerical parser.
sources.push(
  { id: "nasa-maddocks-as4", name: "AS4 / 3501-6 · published model", publisher: "NASA NTRS",
    materials: [{ id: "as4-3501", name: "AS4 / 3501-6" }],
    pageUrl: "https://ntrs.nasa.gov/api/citations/19960008935/downloads/19960008935.pdf", hosts: ["ntrs.nasa.gov"],
    documentPattern: /$a/, identity: [], intervalHours: 24, kind: "reference-document" },
  { id: "icf11-agp370", name: "AGP370 · original experimental paper", publisher: "ICF11",
    materials: [{ id: "agp370", name: "AGP370-5H / 3501-6" }],
    pageUrl: "https://www.gruppofrattura.it/ocs/index.php/ICF/ICF11/paper/download/10515/9871", hosts: ["www.gruppofrattura.it", "gruppofrattura.it"],
    documentPattern: /$a/, identity: [], intervalHours: 24, kind: "reference-document" },
  { id: "chen-2015-ucsd-x840", name: "X840 / Z60 · UC San Diego dissertation (Chen 2015)", publisher: "University of California, San Diego",
    materials: [{ id: "x840-z60-pw", name: "X840 / Z60 plain weave 6K" }],
    pageUrl: "https://escholarship.org/search?q=%22Wide%20Area%20Blunt%20Impact%20Damage%20to%20Composite%20Aircraft%20Structures%22", hosts: ["escholarship.org"],
    documentPattern: /$a/, identity: [], intervalHours: 24, kind: "reference-document" },
  { id: "ncamp-e765-2025", name: "7781 / E-765 · NCAMP property report", publisher: "NIAR / NCAMP",
    materials: [{ id: "7781-e765", name: "7781 / E-765" }],
    pageUrl: "https://www.wichita.edu/industry_and_defense/NIAR/Documents/Park-Aerospace-Corp-7781-E765-Glass-CAM-RP-2023-010-Rev-NC-MPDR-2-25-25.pdf", hosts: ["www.wichita.edu"],
    documentPattern: /$a/, identity: [], intervalHours: 24, kind: "reference-document" },
);

// NCAMP qualification reports and the NASA IM7 / 8552 report for records other than AS4/8552 and 7781/E-765. Registered before
// the loop below so each report attaches to its own record (the IM7 reports also contain "8552").
const ncampRecords: Record<string, { id: string; name: string }> = {
  "im7-data": { id: "im7-8552", name: "IM7 / 8552" }, "im7-stats": { id: "im7-8552", name: "IM7 / 8552" },
  "t650-data": { id: "t650-5320-1", name: "T650 / 5320-1" }, "t650-stats": { id: "t650-5320-1", name: "T650 / 5320-1" },
  "bt250-data": { id: "im7-bt250e-6", name: "IM7 / BT250E-6" }, "bt250-stats": { id: "im7-bt250e-6", name: "IM7 / BT250E-6" },
  "tc380-data": { id: "t1100gc-tc380", name: "T1100GC / TC380" }, "tc380-stats": { id: "t1100gc-tc380", name: "T1100GC / TC380" },
  "ep2190-data": { id: "ims65-ep2190", name: "IMS65 / EP2190" }, "ep2190-stats": { id: "ims65-ep2190", name: "IMS65 / EP2190" },
  "im7-nasa-2023": { id: "im7-8552", name: "IM7 / 8552" }, // NASA/TM-20230001560, second IM7 / 8552 dataset
  "as4pw-data": { id: "as4-8552s-pw", name: "AS4 PW / 8552S" }, "as4pw-stats": { id: "as4-8552s-pw", name: "AS4 PW / 8552S" },
  "t650pw-data": { id: "t650-5320-1-pw", name: "T650 PW / 5320-1" }, "t650pw-stats": { id: "t650-5320-1-pw", name: "T650 PW / 5320-1" },
  "tc250-data": { id: "hts40-tc250", name: "HTS40 PW / TC250" }, "tc250-stats": { id: "hts40-tc250", name: "HTS40 PW / TC250" },
};
// MIL-HDBK-17-2F and its cancellation notice serve two historical records. The ASSIST record page
// is monitored; the PDF itself is stamped per download, so a byte change is a review trigger only.
for (const key of ["milhdbk-17-2f", "milhdbk-17-2f-notice-1"] as const) {
  const reference = qualificationReferences[key];
  sources.push({ id: reference.id, name: reference.title, publisher: reference.publisher,
    materials: [{ id: "t650-35-976", name: "T650-35 / 976" }, { id: "7781-ea9396", name: "7781 / EA 9396" }],
    pageUrl: reference.url, hosts: [new URL(reference.url).hostname],
    documentPattern: /$a/, identity: [], intervalHours: 24 * 7, kind: "reference-document", maxDocumentBytes: 20_000_000 });
}
for (const [key, material] of Object.entries(ncampRecords)) {
  const reference = qualificationReferences[key as keyof typeof qualificationReferences];
  sources.push({ id: reference.id, name: reference.title, publisher: reference.publisher,
    materials: [material], pageUrl: reference.url, hosts: [new URL(reference.url).hostname],
    documentPattern: /$a/, identity: [], intervalHours: 24, kind: "reference-document", maxDocumentBytes: 20_000_000 });
}

// Only public edition/status metadata is retained. No ASTM standard text is stored or sent to AI.
for (const reference of Object.values(qualificationReferences)) {
  if (sources.some(s => s.id === reference.id)) continue;
  const carbon = reference.id.includes("8552");
  sources.push({ id: reference.id, name: reference.title, publisher: reference.publisher,
    materials: [{ id: carbon ? "as4-8552" : "7781-e765", name: carbon ? "AS4 / 8552" : "7781 / E-765" }],
    pageUrl: reference.url, hosts: [new URL(reference.url).hostname], documentPattern: /$a/, identity: [],
    intervalHours: 24, kind: "reference-document", maxDocumentBytes: 20_000_000 });
}

for (const standard of Object.values(standards).filter(s => s.monitorId)) {
  const code = standard.id.startsWith("C") ? `C0${standard.id.slice(1)}_C0${standard.id.slice(1)}M` : ["D1621", "D1623"].includes(standard.id) ? standard.id : `${standard.id}_${standard.id}M`;
  sources.push({ id: standard.monitorId!, name: standard.title, publisher: "ASTM International",
    materials: Object.entries(materialEvidence).filter(([, e]) => e.methodIds.includes(standard.id)).map(([id]) => ({ id, name: id })),
    // Stable family routes follow the active edition instead of remaining on an archived edition page.
    pageUrl: `https://store.astm.org/standards/${standard.id.startsWith("C") ? standard.id.toLowerCase() : code.toLowerCase()}`, hosts: ["store.astm.org", "www.astm.org"], documentPattern: /$a/,
    identity: [], intervalHours: 24, kind: "standard-metadata", standardCode: code });
}
