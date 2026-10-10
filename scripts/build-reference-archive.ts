import { readFile, writeFile, mkdir, readdir, copyFile, stat } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { curatedMaterials, materialDatasets, exportCitedMaterial, archivedMaterialReasons } from "../lib/curated-materials";
import { physicsTopics } from "../lib/physics";
import { standards } from "../lib/material-evidence";
import { materialSource, materials as originalMaterials } from "../lib/materials";

const root = process.cwd();
const digest = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");
const escape = (x: unknown) => String(x ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
const safe = (name: string) => name.replace(/[^a-zA-Z0-9._-]/g, "-");
type Source = { id: string; title: string; publisher: string; date: string | null; revision: string; url: string; sha256: string | null; accessed?: string; kind?: string; page?: number; printedPage?: number; authors?: string; verification?: string };
type Reference = Source & { roles: string[]; localFile: string; localSha256: string; fingerprintCheck: string; bytes: number };

async function main() {
  const destination = path.resolve(root, process.argv[2] || `References/${new Date().toISOString().slice(0, 10)}`);
  const allowed = path.resolve(root, "References") + path.sep;
  if (!destination.startsWith(allowed)) throw Error("Archive destination must be inside this project's References folder.");
  try { await stat(destination); throw Error(`Archive already exists: ${destination}. Choose a new snapshot folder; existing evidence is never overwritten.`); }
  catch (e) { if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e; }

  const datasets = curatedMaterials.flatMap(materialDatasets);
  const sources = new Map<string, { source: Source; roles: Set<string>; group: string }>();
  const register = (source: Source, role: string, group: string) => {
    const existing = sources.get(source.id);
    if (existing && existing.source.sha256 !== source.sha256) throw Error(`Conflicting source fingerprints: ${source.id}`);
    if (existing) existing.roles.add(role);
    else sources.set(source.id, { source, roles: new Set([role]), group });
  };
  for (const m of datasets) {
    const group = m.source.kind === "book" ? "01-Books" : /Manufacturer/.test(m.dataset) ? "03-Manufacturer-Datasheets" : "02-Reports";
    register(m.source, `Property source: ${m.name} / ${m.datasetId}`, group);
    for (const s of m.supportingReferences || []) register(s, `${s.role}: ${m.name}`, /specification/i.test(s.title) ? "04-Specifications" : "02-Reports");
  }
  const book = datasets.find(m => m.source.kind === "book")!.source;
  register(book, "Source for all 29 current physics equation cards", "01-Books");
  for (const [key, title, date, revision] of [
    ["volume-2", "Composite Materials Handbook · Volume 2: Polymer Matrix Composites, Materials Properties", "2002", "MIL-HDBK-17-2F"],
    ["volume-3", "Composite Materials Handbook · Volume 3: Materials Usage, Design, and Analysis", "2012", "CMH-17-3G"],
  ]) {
    const metadata = JSON.parse(await readFile(path.join(root, `.local/cmh17/${key}-metadata.json`), "utf8"));
    register({ id: key, title, date, revision, publisher: "As identified in supplied handbook", url: "", sha256: metadata.sha256 }, "User-supplied background handbook; not a numerical source for the current released property records", "01-Books");
  }
  const schoolPath = path.join(root, materialSource.localPath);
  const schoolBytes = await readFile(schoolPath);
  register({ id: "original-school-appendix", title: "Original supplied material-properties appendix", publisher: "User-supplied course material", date: null, revision: path.basename(materialSource.localPath), url: "", sha256: digest(schoolBytes) }, "Historical import and reconciliation only; not substituted for current cited datasets", "05-Original-Import");

  const candidates = [schoolPath,
    path.join(process.env.USERPROFILE!, "Downloads/Engineering Mechanics of Composite Materials -- Isaac M. Daniel Ori lshai -- WeLib.org.pdf"),
    path.join(process.env.USERPROFILE!, "Downloads/Composite materials handbook volume 2 _ polymer matrix composites.pdf"),
    path.join(process.env.USERPROFILE!, "Downloads/Composite materials handbook. Volume 3, Polymer matrix composites _ materials usage, design, and analysis.pdf"),
  ];
  for (const dir of [".local/material-audit", ".local/qualification"])
    for (const file of await readdir(path.join(root, dir))) if (file.toLowerCase().endsWith(".pdf")) candidates.push(path.join(root, dir, file));
  const byHash = new Map<string, { file: string; size: number }>();
  for (const file of candidates) {
    const bytes = await readFile(file);
    if (bytes.subarray(0, 5).toString() !== "%PDF-") throw Error(`Not a PDF: ${file}`);
    byHash.set(digest(bytes), { file, size: bytes.length });
  }
  // Preflight every required document before creating the archive.
  for (const { source } of sources.values()) if (!source.sha256 || !byHash.has(source.sha256)) throw Error(`Exact referenced PDF is unavailable: ${source.id}`);
  await mkdir(destination, { recursive: true });
  const references: Reference[] = [];
  for (const { source, roles, group } of sources.values()) {
    const found = byHash.get(source.sha256!)!;
    const localFile = `${group}/${safe(source.id)}.pdf`;
    await mkdir(path.join(destination, group), { recursive: true });
    await copyFile(found.file, path.join(destination, localFile));
    const actual = digest(await readFile(path.join(destination, localFile)));
    if (actual !== source.sha256) throw Error(`Copy failed fingerprint verification: ${source.id}`);
    references.push({ ...source, roles: [...roles], localFile, localSha256: actual,
      fingerprintCheck: source.id === "original-school-appendix" ? "Matched copied original import; SHA-256 captured for this archive" : "Matched existing library or supplied-document SHA-256", bytes: found.size });
  }
  const referenceById = new Map(references.map(r => [r.id, r]));
  const saveJson = async (file: string, data: unknown) => { await mkdir(path.dirname(path.join(destination, file)), { recursive: true }); await writeFile(path.join(destination, file), JSON.stringify(data, null, 2) + "\n"); };
  const datasetFiles: { id: string; name: string; dataset: string; file: string; sourceId: string; properties: number }[] = [];
  for (const material of datasets) {
    const file = `06-Dataset-Records/${safe(material.id)}--${safe(material.datasetId)}.json`;
    const ref = referenceById.get(material.source.id)!;
    await saveJson(file, { ...exportCitedMaterial(material), archiveReference: {
      sourceId: ref.id, localDocument: `../${ref.localFile}`, sha256: ref.localSha256,
      propertyPageConvention: "sourcePage is the 1-based PDF viewer page; printedPage is the page printed in the publication, when recorded",
    }, supportingLocalDocuments: (material.supportingReferences || []).map(r => ({ sourceId: r.id, localDocument: `../${referenceById.get(r.id)!.localFile}`, sha256: r.sha256 })) });
    datasetFiles.push({ id: material.datasetId, name: material.name, dataset: material.dataset, file, sourceId: ref.id, properties: material.properties.length });
  }
  const formulas = physicsTopics.flatMap(t => t.methods.map(m => ({ topic: t.title, name: m.name, equation: m.equation, assumptions: t.assumptions,
    detail: m.detail, units: m.units, reference: m.reference, sourceId: book.id, localDocument: referenceById.get(book.id)!.localFile,
    pageConvention: "Formula locations cite printed textbook pages, not PDF viewer page numbers" })));
  await saveJson("formula-traceability.json", formulas);
  await saveJson("standards-links.json", { note: "Official links retained from the project registry; full standard texts are not included. These catalog links do not replace historical test-method editions cited in reports. No online currency check was performed when packaging this archive.", references: Object.values(standards) });
  const methods = new Map<string, string[]>();
  for (const m of datasets) for (const p of m.properties) methods.set(p.method, [...(methods.get(p.method) || []), `${m.datasetId} / ${p.key}`]);
  await saveJson("test-method-traceability.json", [...methods].map(([method, propertyRecords]) => ({ method, propertyRecords })));
  await saveJson("05-Original-Import/original-records.json", { sourceId: "original-school-appendix", localDocument: "original-school-appendix.pdf", originalMaterials, archivedMaterialReasons,
    use: "Historical source transcription; not the active material library" });
  await mkdir(path.join(destination, "07-Review-Notes"), { recursive: true });
  const notes = (await readdir(path.join(root, "docs"))).filter(f => /^(material-|textbook-|qualification-|physics-foundations)/.test(f) && f.endsWith(".md"));
  for (const note of notes) await copyFile(path.join(root, "docs", note), path.join(destination, "07-Review-Notes", note));
  const createdAt = new Date().toISOString();
  await saveJson("manifest.json", { schemaVersion: 1, createdAt, scope: "Snapshot of bundled released material datasets and current equation references, with supporting and historical documents clearly identified",
    materials: curatedMaterials.length, datasetCount: datasets.length, propertyCount: datasets.reduce((n, m) => n + m.properties.length, 0), references, datasets: datasetFiles,
    formulaIndex: "formula-traceability.json", standardLinks: "standards-links.json", testMethodIndex: "test-method-traceability.json" });
  const link = (url: string, label: string) => `<a href="${escape(url)}">${escape(label)}</a>`;
  const sourceRows = references.map(r => `<tr><td>${link(r.localFile, r.title)}<small>${escape(r.id)}</small></td><td>${escape(r.publisher)}<br>${escape(r.date || "Publication date not established")}<br>${escape(r.revision)}</td><td>${r.roles.map(escape).join("<br>")}</td><td>${r.url ? link(r.url, "Publisher / original source") : "Supplied locally"}<details><summary>File fingerprint</summary><code>${r.localSha256}</code><p>${escape(r.fingerprintCheck)}</p></details></td></tr>`).join("");
  const datasetSections = datasets.map((m, i) => {
    const ref = referenceById.get(m.source.id)!;
    const rows = exportCitedMaterial(m).properties.map(p => `<tr><td>${escape(p.label)}<small>${escape(p.key)} · ${escape(p.basis)}</small></td><td>${escape(p.displayUnits.english)}</td><td>${escape(p.displayUnits.si)}</td><td>${link(`${ref.localFile}#page=${p.sourcePage}`, `PDF p. ${p.sourcePage}`)}${p.printedPage ? `<br>Printed p. ${p.printedPage}` : ""}<small>${escape(p.evidence)}</small></td><td>${escape(p.method)}<small>${escape(p.conditions)}</small></td></tr>`).join("");
    return `<details class="dataset"><summary>${escape(m.name)} — ${escape(m.dataset)} (${m.properties.length} properties)</summary><p>${escape(m.datasetId)}<br>${escape(m.application)}<br>${escape(m.conditions)}</p><p>${link(ref.localFile, "Open source PDF")} · ${link(datasetFiles[i].file, "Dataset JSON")}</p><div class="scroll"><table><thead><tr><th>Property / basis</th><th>English</th><th>SI</th><th>Source location</th><th>Method / conditions</th></tr></thead><tbody>${rows}</tbody></table></div></details>`;
  }).join("");
  const formulaRows = formulas.map(f => `<tr><td>${escape(f.topic)}<br><strong>${escape(f.name)}</strong></td><td>${escape(f.reference?.location)}</td><td>${link(f.localDocument, "Open textbook")}<small>Printed page references</small></td></tr>`).join("");
  const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reference archive — ${createdAt.slice(0, 10)}</title><style>body{font:16px/1.55 system-ui,sans-serif;color:#182520;background:#f5f7f4;margin:0}main{max-width:1450px;margin:auto;padding:40px 28px}h1{font-size:36px;line-height:1.2}h2{margin-top:40px}a{color:#216047}small{display:block;color:#53645b;margin-top:5px}table{width:100%;border-collapse:collapse;background:white;font-size:14px}th,td{padding:13px;text-align:left;vertical-align:top;border-bottom:1px solid #dce3dd}th{background:#e6eee7}code{overflow-wrap:anywhere}input{font:inherit;padding:12px;width:min(600px,90%);border:1px solid #abc0b0;border-radius:5px}.dataset{padding:18px;background:white;border:1px solid #dce3dd;margin:10px 0}summary{cursor:pointer;font-weight:600}.scroll{overflow-x:auto}nav{display:flex;gap:20px;flex-wrap:wrap}.note{padding:15px 20px;background:#e6eee7;border-radius:5px}.hidden{display:none}@media(max-width:600px){main{padding:24px 14px}h1{font-size:28px}}</style><main>
<h1>Material &amp; physics reference archive</h1><p>${curatedMaterials.length} materials · ${datasets.length} datasets · ${datasets.reduce((n, m) => n + m.properties.length, 0)} property entries · ${formulas.length} formula cards · ${references.length} PDFs</p><p>Snapshot created ${escape(createdAt)}. Open any material below to trace each value to its original PDF page. This folder works offline; publisher links need an internet connection.</p>
<nav><a href="#documents">Documents</a><a href="#materials">Material values</a><a href="#formulas">Formula references</a><a href="#standards">Standards</a><a href="#notes">Review notes</a>${link("manifest.json", "Full manifest")}</nav>
<p class="note">The PDF fingerprints match the recorded sources. A matching fingerprint confirms the document version; it does not certify a material or its design allowables. Textbooks, handbooks and the original course appendix remain local to this reference archive. Historical review notes describe the releases at their dates; the current snapshot is indexed here.</p>
<h2 id="documents">Source documents</h2><label for="search">Find a document, material or formula</label><br><input id="search" type="search" placeholder="AS4, glass, density, laminate…"><div class="scroll"><table id="documents-table"><thead><tr><th>Document</th><th>Publisher / date / edition</th><th>Used for</th><th>Original link / fingerprint</th></tr></thead><tbody>${sourceRows}</tbody></table></div>
<h2 id="materials">Material-to-property traceability</h2><p>PDF page links use the viewer's page number. Printed page numbers are shown separately where recorded. Ranges and lower bounds are retained in the JSON exports; they are not single-value model inputs.</p>${datasetSections}
<h2 id="formulas">Formula references</h2><p>All current equation cards cite Daniel &amp; Ishai. ${link("formula-traceability.json", "Complete formula metadata")}</p><div class="scroll"><table id="formula-table"><thead><tr><th>Equation</th><th>Printed source location</th><th>Document</th></tr></thead><tbody>${formulaRows}</tbody></table></div>
<h2 id="standards">Standards &amp; test methods</h2><p>Full ASTM, ISO and SAE standard texts are not included. These official catalog links are the project's saved references; use the exact historical edition stated in each property's test method when reproducing that report. ${link("test-method-traceability.json", "Every cited test method and its property records")}</p><ul>${Object.values(standards).map(s => `<li>${link(s.url, s.title)}</li>`).join("")}</ul>
<h2 id="notes">Review history</h2><ul>${notes.map(n => `<li>${link(`07-Review-Notes/${n}`, n)}</li>`).join("")}</ul><p>${link("CHECKSUMS.sha256", "All archived file fingerprints")} · ${link("README.txt", "Folder guide")}</p>
</main><script>document.getElementById('search').addEventListener('input',function(){const q=this.value.toLowerCase();document.querySelectorAll('#documents-table tbody tr,#formula-table tbody tr,.dataset').forEach(el=>el.classList.toggle('hidden',!el.textContent.toLowerCase().includes(q)));});</script></html>`;
  await writeFile(path.join(destination, "index.html"), html);
  await writeFile(path.join(destination, "README.txt"), `REFERENCE ARCHIVE\nCreated: ${createdAt}\n\nSTART HERE: Open index.html in a browser.\n\n01-Books: supplied textbook and handbook editions.\n02-Reports: NASA, research, qualification and statistical reports.\n03-Manufacturer-Datasheets: exact supplier PDFs used in the library.\n04-Specifications: supporting material and process specifications.\n05-Original-Import: original course appendix and historical transcription.\n06-Dataset-Records: all released property records, exact source locations and unit conversions.\n07-Review-Notes: dated research, corrections and validation notes.\n\nmanifest.json links document IDs, publication dates, revisions, fingerprints, datasets and local files.\nformula-traceability.json lists all current equation citations and assumptions.\ntest-method-traceability.json maps every reported method to property records.\nstandards-links.json contains official catalog links; full standards are not included.\nCHECKSUMS.sha256 covers every other file in this snapshot.\n\nThis is a dated snapshot, not a live-updating folder. Keep it intact when referencing an analysis. New reviewed releases should get a new folder. Existing publication-monitoring schedules are unchanged.\nThe References folder is excluded from Git and is outside the website's public assets.\n\nThe numerical dataset exports are schema 2: valueType distinguishes scalar, range and lower-bound values. A book's printed page is not necessarily its PDF viewer page.\nThe supplied handbooks are background references; their inclusion does not mean their tables were imported into the current catalog.\nHistorical school records and earlier review notes are not current material releases.\n`);
  const files: string[] = [];
  async function walk(dir: string) { for (const entry of await readdir(dir, { withFileTypes: true })) { const full = path.join(dir, entry.name); if (entry.isDirectory()) await walk(full); else files.push(full); } }
  await walk(destination);
  const checksums = [];
  for (const file of files.sort()) checksums.push(`${digest(await readFile(file))}  ${path.relative(destination, file).split(path.sep).join("/")}`);
  await writeFile(path.join(destination, "CHECKSUMS.sha256"), checksums.join("\n") + "\n");
  console.log(JSON.stringify({ destination, documents: references.length, datasets: datasets.length, properties: datasets.reduce((n, m) => n + m.properties.length, 0), formulas: formulas.length, files: files.length + 1 }));
}
main().catch(e => { console.error(e); process.exitCode = 1; });
