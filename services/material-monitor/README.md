# Material source monitor

Local, persistent manufacturer-document and ASTM edition monitoring. This is a TypeScript/Node.js service, separate from the static website. It uses SQLite and Mozilla PDF.js; it has no LLM connection and sends no customer data to publishers or an AI provider.

## Run

Requires Node.js 24 or newer. From the repository root:

```sh
npm install
npm run monitor:start
```

Open http://127.0.0.1:3210. The service immediately checks sources that are due, then checks the schedule every minute. Each successful source is due again in 24 hours. Failures retry after 15 minutes, increasing to a maximum of six hours. Source failures remain visible alongside the last successful check. The monitor must remain running on an awake machine; no OS service, external scheduler, email alert, or cloud deployment is installed. On restart, overdue checks run again.

For an external scheduler, the one-shot command checks only due sources and exits nonzero on failures:

```sh
npm run monitor:check
npm run monitor:check -- --force
npm run test:monitor
```

`MATERIAL_MONITOR_DB` overrides the default `.local/services/material-monitor/monitor.sqlite`. `MATERIAL_MONITOR_PORT` overrides port 3210. Original PDFs, full extracted text and reviewer identities/notes remain in the ignored local SQLite database. A sanitized public feed contains source metadata, structured candidates and released reference properties. Back up SQLite consistently (stop the service before copying its database files).

## Behavior

1. Re-discover exactly one matching PDF from each official product page. No fixed dated URL and no guessing between competing candidates. ASTM adapters inspect stable standard-family pages and retain only public active-edition/catalog update metadata, not licensed standard text.
2. Follow only HTTPS destinations on the source's explicit host allowlist, including redirects. Bound download time, size, parse time, page count, and parser output. Parse PDFs in a disposable subprocess. This reduces exposure but is not an OS sandbox.
3. Validate extractable text and expected product-family identifiers. Exact grade applicability is a human review responsibility. Scan-only, ambiguous, inaccessible, or structurally changed sources fail visibly rather than becoming empty updates.
4. Store immutable PDF snapshots keyed by SHA-256, page text, source URLs, capture times, and all check outcomes. A database lease prevents overlapping checks. Duplicate documents reuse their existing snapshot. No document date is inferred from a URL or treated as a material measurement date.
5. Compare extracted page text with the last accepted source, or the previous captured source if none was accepted. Binary-only changes still require review because text comparisons do not detect changed graphics. Narrow adapters extract candidates for H45, H250, HRH-10 1/8-1.8 and M55J/EX-1515, validating column order, units, reported methods, conditions and nominal/minimum ordering. M55J data is specifically the manufacturer's 121°C autoclave dataset; it cannot replace the school's vacuum-oven dataset. Conflicting SI/US pairs are flagged and excluded from manufacturer property exports. Changed layouts or conditions stop extraction visibly; other sources have no numerical adapter.
6. Accept or reject the current source revision with an operator name and note. Reviews are append-only. Stale screens, failed checks, overdue checks and duplicate decisions are blocked. A source review alone cannot publish properties. Separately verify every candidate value against the original and publish a reference revision in the console. It retains its release ID, source fingerprint, revision/date, page evidence, units, basis, conditions, direction and approval date. It is never a qualified design allowable. Later source updates leave existing releases unchanged.

## Coverage and website feed

The public catalog contains eight independently cited datasets; fourteen original imports are excluded from lookup and retained for investigation. See [the reference audit](../../docs/material-research-audit-2026-10-01.md). Six manufacturer adapters track Diab H, Hexcel HRH-10, Hexcel CR III, BALTEK SBC, Toray EX-1515 and Park E-765. BALTEK remains an investigation source. Four reviewed supplier releases are bundled; the website accepts newer releases only when source and property definitions remain compatible.

Three `reference-document` adapters track fixed NASA, ICF11 and NCAMP publication URLs. They validate bounded, allowlisted PDF downloads and compare byte fingerprints, without sending long/scanned reports through the numerical extractor. These checks detect replacement at an existing URL, not new papers or new filenames. The final NASA, ICF11 and NCAMP checks succeeded. NCAMP access was intermittent during research; access-challenge HTML fails the PDF check and is retried. Research/CR III numerical updates require a reviewed code/data release; they cannot be published by the current manufacturer-property console.

Eight ASTM adapters track D3039, D6641, D5379, D5766, C273, C365, D1621 and D1623. ISO 845 and SAE AMS-STD-401 are reference links only, without automatic revision monitoring. The NCAMP E765 record cites a specific property report and measured means; no statistical allowables are assigned. A standard update requires impact review; it never changes the method edition reported for an old measurement.

Dates come only from explicit source evidence. Month-only dates remain month-only. Copyright, crawl and upload dates are not revision dates. ASTM catalog update dates are labeled separately from material revisions. The public lookup shows a clearly labeled access date when no publication/revision date is established.

The service atomically writes `public/materials/catalog-status.json` and also updates `out/materials/catalog-status.json` if an export exists. This generated feed is ignored by Git. It excludes original documents, full source text, reviewer names/notes, paths and tokens. The website refreshes it every 30 seconds. A missing feed, request failure or heartbeat older than three minutes marks monitoring unavailable; each source also reports failure/overdue status. The running service refreshes its heartbeat every minute. One-shot-only deployments lose the live-connected indication between runs.

A remote static host requires a persistent worker and protected publication of the feed with caching disabled; uploading `out/` alone does not provide automatic monitoring. Run `npm test` for monitor, provenance and product tests.

## Boundaries and next increments

- This is a local operator console, bound to loopback with Host/Origin validation, a mutation token, no cross-origin access, and restrictive browser headers. Operator names are self-reported. It is **not** production authentication, tenant isolation, encryption at rest, external audit storage, or an ITAR-compliant deployment. Do not store customer-controlled data here.
- Publisher PDFs are untrusted reference evidence. The console renders extracted content only as text and downloads originals as attachments. Source documents cannot issue commands. Stored copies are for internal review; public accessibility does not establish commercial redistribution or training rights.
- No manufacturer or standards organization push feed is connected. Changes are discovered on the next scheduled check, not instantly. Licensed sources and additional material identities need separately reviewed adapters and access terms.
- No qualified design-allowable release exists. `requireEngineeringProperties` is the strict qualified-design boundary and fails closed for all current records. For preliminary analysis, `analysisPacket` in `lib/material-analysis.ts` offers a separate purpose-specific path: it requires complete unflagged inputs, supported unit conversions, elastic consistency where applicable, and explicit acknowledgement of material/condition assumptions. It pins source evidence and records SI/sign conversions without filling missing values. All 22 classroom records have been audited against the school PDF; this establishes transcription fidelity, not physical qualification. Manufacturer reference minima are not statistical allowables. The current chat is a scope preview, not a solver.
- AI comparison can be added behind a bounded extraction interface after choosing an authorized model/deployment. Require evidence locations, validate every proposal, and deny the model write access to accepted records. AI must never be required for routine unchanged-source checks.
- Production work needs a persistent host/service, notifications and health monitoring, authenticated reviewer identities, access controls, backup/recovery, source-access licensing, deployment-specific compliance review, and process-level isolation for document parsing.

## Extending the source registry

The first carbon/glass qualification release adds the AS4/8552 data, statistical report and specifications, plus the original 7781/E765 AGATE report and later NCAMP specifications/equivalency report. Their registry is derived from `lib/qualification-references.json`; reference downloads allow up to 20 MB because the original AGATE PDF is 13.6 MB. These remain fixed-URL byte checks, with reviewed numerical releases. See `docs/qualification-records-2026-10-01.md` for source dates, scope and the historical AGATE endpoint's TLS limitation.

Add a reviewed entry in `sources.ts`: unique ID, exact material links, publisher URL, permitted hosts, a document selector, identity checks, and interval. Include discovery fixtures for missing/ambiguous links. A new material system is a new record, not a replacement based on similar names. Do not expose a free-form URL fetch endpoint.
