// All publisher text is rendered with textContent, never as HTML or executable instructions.
const $ = id => document.getElementById(id);
let token = "";
let selected = null;
let current = null;
let busy = false;
const date = value => value ? new Date(value).toLocaleString() : "Not yet checked";
function element(tag, text, className) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (className) e.className = className; return e; }
function link(text, href) { const e = element("a", text); e.href = href; e.target = "_blank"; e.rel = "noreferrer"; return e; }
function feedback(text) { $("feedback").textContent = text; }
async function api(path, data) {
  const response = await fetch(path, data ? { method: "POST", headers: { "Content-Type": "application/json", "X-Monitor-Token": token }, body: JSON.stringify(data) } : {});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed");
  return result;
}
function status(source) {
  if (source.error) return "Check failed";
  if (!source.current) return "Awaiting first check";
  if (source.overdue) return "Check due";
  return source.review ? `Source ${source.review.decision}` : "Review required";
}
async function refresh() {
  try {
    const data = await api("/api/status");
    token = data.token; busy = data.busy;
    $("check").disabled = busy;
    $("check").textContent = busy ? "Checking sources…" : "Check sources now";
    $("schedule").textContent = data.schedule;
    if (data.workerError) feedback(data.workerError);
    $("sources").replaceChildren();
    for (const source of data.sources) {
      const card = element("article", undefined, "card");
      card.append(element("span", status(source), `badge ${source.error || !source.review ? "alert" : ""}`), element("h2", source.name), element("p", source.materials.map(m => m.name).join(" · ")));
      const fields = element("dl");
      for (const [name, value] of [["Publisher", source.publisher], ["Last successful check", date(source.last_success)], ["Next check", source.last_attempt ? date(source.next_check) : "On service startup"], ["Latest result", source.lastCheck?.message || "No source captured"], ["Engineering release", "None — references only"]]) fields.append(element("dt", name), element("dd", value));
      card.append(fields);
      if (source.error) card.append(element("p", source.error));
      const button = element("button", "Review source", "secondary");
      button.onclick = () => show(source.id).catch(e => feedback(e.message));
      card.append(button);
      $("sources").append(card);
    }
    if (selected) {
      const source = data.sources.find(s => s.id === selected);
      $("save-review").disabled = busy || !!source?.error || !!source?.overdue;
      if (current && (source?.current?.id !== current.source.current?.id || source?.review?.decision !== current.source.review?.decision)) await show(selected, false);
    }
  } catch (error) {
    feedback(`Monitor unavailable: ${error.message}. Displayed data may be stale.`);
    $("save-review").disabled = true;
  }
}
async function show(id, scroll = true) {
  const detail = await api(`/api/source?id=${encodeURIComponent(id)}`);
  selected = id; current = detail;
  const source = detail.source;
  const format = source.kind === "standard-metadata" ? "catalog metadata" : "PDF";
  $("detail").hidden = false;
  $("detail-name").textContent = source.name;
  $("comparison-note").textContent = detail.baselineId ? `Comparing with source snapshot #${detail.baselineId}. These are page text differences, not verified property changes. Graphics and table alignment require inspection of the PDF.` : "First capture: no previous source baseline exists. Inspect this document before accepting it for reference.";
  $("document-links").replaceChildren(link("Publisher source page", source.pageUrl));
  if (source.current) $("document-links").append(link(`Download captured ${format}`, `/api/document?id=${source.current.id}`));
  if (detail.baselineId) $("document-links").append(link(`Download comparison ${format}`, `/api/document?id=${detail.baselineId}`));
  if (source.kind === "standard-metadata") $("comparison-note").textContent = "Only public active-edition and catalog update metadata is compared. Review the licensed standard separately to determine engineering impact.";
  $("changes").replaceChildren();
  for (const change of detail.changes) {
    const section = element("details"); section.open = detail.changes.length === 1;
    section.append(element("summary", `Page ${change.page} · ${change.before ? "text changed" : "new page"}`));
    const comparison = element("div", undefined, "comparison");
    for (const [label, text] of [["Previous source", change.before], ["Current source", change.after]]) {
      const column = element("div"); column.append(element("h3", label), element("pre", text || "No page in this version")); comparison.append(column);
    }
    section.append(comparison); $("changes").append(section);
  }
  if (!detail.changes.length) $("changes").append(element("p", source.current ? "No extracted text differences. Inspect the PDF for graphic, layout, and metadata changes." : "No document available. Check sources to establish a baseline."));
  $("full-text").replaceChildren();
  for (const page of detail.pages) $("full-text").append(element("h3", `Page ${page.page}`), element("pre", page.text));
  $("review-form").hidden = !source.current || !!source.review;
  $("save-review").disabled = busy || !!source.error || source.overdue;
  $("review-form").reset();
  $("review-state").textContent = source.review ? `Source ${source.review.decision} by ${source.review.reviewer} on ${date(source.review.reviewed_at)}. ${source.review.note}` : "A source review does not authorize publishing this document or using its values for design.";
  $("history").replaceChildren();
  for (const item of detail.history) {
    const p = element("p", `Snapshot #${item.id} · ${date(item.captured_at)} · SHA-256 ${item.raw_hash.slice(0, 16)}… `);
    p.append(link("Download", `/api/document?id=${item.id}`)); $("history").append(p);
  }
  for (const review of detail.reviews) $("history").append(element("p", `Snapshot #${review.snapshot_id} · ${review.decision} · ${review.reviewer} · ${date(review.reviewed_at)} · ${review.note}`));
  $("checks").replaceChildren();
  for (const check of detail.checks) $("checks").append(element("p", `${date(check.checked_at)} · ${check.outcome} · ${check.message}`));
  await showCandidates(id);
  if (scroll) $("detail").scrollIntoView({ behavior: "smooth", block: "start" });
}
async function showCandidates(sourceId) {
  const catalog = await api("/api/catalog");
  const candidates = catalog.candidates.filter(c => c.sourceId === sourceId);
  const extractionFailed = catalog.sources.find(s => s.id === sourceId)?.propertyExtraction === "review-required";
  $("reference-publication").hidden = candidates.length === 0 && !extractionFailed;
  $("reference-candidates").replaceChildren();
  if (extractionFailed) $("reference-candidates").append(element("p", "Property extraction stopped because the table or conditions changed. Review the adapter and original source; no candidate values were published."));
  for (const candidate of candidates) {
    const section = element("section");
    section.append(element("h3", candidate.materialId));
    const text = candidate.properties.map(p => `${p.label} | ${p.direction} | ${p.value} ${p.unit} | ${p.basis}\n${p.method} | ${p.conditions} | Source page ${p.sourcePage}`).join("\n\n");
    section.append(element("pre", text));
    const published = catalog.releases.find(r => r.materialId === candidate.materialId && r.fingerprint === candidate.fingerprint);
    if (published) section.append(element("p", `Reference released ${date(published.approvedAt)} · ${published.releaseId}`));
    else if (current.source.review?.decision !== "accepted") section.append(element("p", "Accept the source revision first, then verify and publish these reference values."));
    else {
      const form = element("form");
      const reviewerLabel = element("label", "Reviewer name"); const reviewer = element("input"); reviewer.required = true; reviewer.maxLength = 120; reviewerLabel.append(reviewer);
      const noteLabel = element("label", "Property verification findings"); const note = element("textarea"); note.required = true; note.maxLength = 3000; note.rows = 3; noteLabel.append(note);
      const confirmation = element("label", undefined, "confirm"); const checkbox = element("input"); checkbox.type = "checkbox"; checkbox.required = true; confirmation.append(checkbox, document.createTextNode("I verified every proposed value, unit, basis, direction, condition and source page against the original document. This release is reference-only."));
      const submit = element("button", "Publish reference revision"); submit.type = "submit";
      form.append(reviewerLabel, noteLabel, confirmation, submit);
      form.onsubmit = async e => { e.preventDefault(); submit.disabled = true; try { const result = await api("/api/publish-reference", { materialId: candidate.materialId, fingerprint: candidate.fingerprint, reviewer: reviewer.value, note: note.value }); feedback(result.message); await showCandidates(sourceId); } catch (error) { feedback(error.message); submit.disabled = false; } };
      section.append(form);
    }
    $("reference-candidates").append(section);
  }
}
$("check").onclick = async () => { try { await api("/api/check", {}); feedback("Source check started."); await refresh(); } catch (error) { feedback(error.message); } };
$("close").onclick = () => { selected = null; current = null; $("detail").hidden = true; };
$("review-form").onsubmit = async event => {
  event.preventDefault();
  $("save-review").disabled = true;
  try {
    const result = await api("/api/review", { snapshotId: current.source.current.id, decision: $("decision").value, reviewer: $("reviewer").value, note: $("note").value });
    feedback(result.message); await refresh();
  } catch (error) { feedback(error.message); $("save-review").disabled = busy; }
};
void refresh();
setInterval(refresh, 5000);
