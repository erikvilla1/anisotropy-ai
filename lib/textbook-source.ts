// What a customer may read about the textbook. How it was checked, and the evidence for its
// rights class, live in lib/source-provenance.ts, which no page imports (ADR-0018 amendment 2).
export const textbookSource = {
  id: "daniel-ishai-2006", kind: "book" as const,
  title: "Engineering Mechanics of Composite Materials", authors: "Isaac M. Daniel and Ori Ishai",
  publisher: "Oxford University Press", date: "2006", revision: "Second edition · ISBN 978-0-19-515097-1",
  url: "https://global.oup.com/academic/product/engineering-mechanics-of-composite-materials-9780195150971",
  accessed: "2026-10-01",
  rights: "licensed-reference" as const,
  /** The book cited the same way everywhere: the short form in running text, the full form in a reference line. */
  shortCitation: "Daniel & Ishai (2006)",
  fullCitation: "Daniel & Ishai, Engineering Mechanics of Composite Materials, 2nd ed., Oxford University Press, 2006",
  /** The one sentence a customer reads about this source's rights. */
  rightsNote: "Copyrighted textbook. Values are cited by table and printed page; consult your own copy.",
};

// Citation locations only. A link names the printed page; the PDF page stays internal.
export const textbookPages = [
  { pdfPage: 397, printedPage: 377, table: "A.4", title: "Typical unidirectional composites" },
  { pdfPage: 398, printedPage: 378, table: "A.4", title: "Typical unidirectional composites (continued)" },
  { pdfPage: 399, printedPage: 379, table: "A.5", title: "Typical fabric composites" },
  { pdfPage: 400, printedPage: 380, table: "A.6", title: "Three-dimensional composite properties" },
];
