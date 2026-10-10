export const textbookSource = {
  id: "daniel-ishai-2006", kind: "book" as const,
  title: "Engineering Mechanics of Composite Materials", authors: "Isaac M. Daniel and Ori Ishai",
  publisher: "Oxford University Press", date: "2006", revision: "Second edition · ISBN 978-0-19-515097-1",
  url: "https://global.oup.com/academic/product/engineering-mechanics-of-composite-materials-9780195150971",
  accessed: "2026-10-01", sha256: "8c46dbb6cc5d485aaa5a256b9e10c93fd4ee40eb86dc9973ecdb833b4ec729d2",
  verification: "Named column visually checked in the supplied second-edition PDF. Fingerprint identifies that PDF, not the publisher catalog page. SI column retained; imperial display calculated from SI.",
  rights: "licensed-reference" as const,
  rightsEvidence: "Copyrighted textbook; no redistribution permission recorded (ADR-0010). Individual values are cited by table and printed page; scans and extracted text stay local.",
};

// Citation locations only. Original page images stay in ignored local storage.
export const textbookPages = [
  { pdfPage: 397, printedPage: 377, table: "A.4", title: "Typical unidirectional composites" },
  { pdfPage: 398, printedPage: 378, table: "A.4", title: "Typical unidirectional composites (continued)" },
  { pdfPage: 399, printedPage: 379, table: "A.5", title: "Typical fabric composites" },
  { pdfPage: 400, printedPage: 380, table: "A.6", title: "Three-dimensional composite properties" },
];
