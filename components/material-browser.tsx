"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowDownToLine, ArrowUpRight, Layers3, Search } from "lucide-react";
import { materials, materialSource } from "@/lib/materials";
import { downloadFile } from "@/lib/demo";

export function MaterialBrowser() {
  const [search, setSearch] = useState("");
  const [family, setFamily] = useState("All families");
  const [selected, setSelected] = useState(materials[0].id);
  const filtered = materials.filter(
    (m) =>
      (family === "All families" || m.family === family) &&
      `${m.name} ${m.family} ${m.architecture} ${m.process}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()),
  );
  const current = filtered.find((m) => m.id === selected) || filtered[0];
  return (
    <>
      <div className="library-filters">
        <label className="library-search">
          <Search size={17} />
          <input
            aria-label="Search materials"
            placeholder="Search a material, process, or architecture…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Filter material family"
          value={family}
          onChange={(e) => setFamily(e.target.value)}
        >
          {[
            "All families",
            "Carbon / epoxy",
            "Glass / epoxy",
            "Sandwich cores",
          ].map((f) => (
            <option key={f}>{f}</option>
          ))}
        </select>
        <span aria-live="polite">{filtered.length} source records</span>
      </div>
      {current ? (
        <div className="material-browser source-materials">
          <div className="material-list" aria-label="Material records">
            {filtered.map((m) => (
              <button
                key={m.id}
                aria-pressed={current.id === m.id}
                onClick={() => setSelected(m.id)}
              >
                <Layers3 size={18} />
                <span>
                  <strong>{m.name}</strong>
                  <small>
                    {m.architecture} · {m.basis}
                  </small>
                </span>
                {(m.note || m.properties.some((p) => p.review)) && (
                  <span
                    className="review-dot"
                    title="Source review needed"
                    aria-label="Source review needed"
                  />
                )}
              </button>
            ))}
          </div>
          <article className="material-detail" aria-label="Selected material">
            <div className="material-detail-title">
              <div>
                <span className="eyebrow">
                  {current.family} / {current.section}
                </span>
                <h2>{current.name}</h2>
              </div>
              <Layers3 size={32} strokeWidth={1} />
            </div>
            <dl className="material-context">
              <div>
                <dt>Architecture</dt>
                <dd>{current.architecture}</dd>
              </div>
              <div>
                <dt>Process</dt>
                <dd>{current.process}</dd>
              </div>
              <div>
                <dt>Source basis</dt>
                <dd>{current.basis}</dd>
              </div>
            </dl>
            <div className="source-toolbar">
              <span>ORIGINAL SOURCE UNITS</span>
              <a
                href={`${materialSource}#page=${current.page}`}
                target="_blank"
                rel="noreferrer"
              >
                Appendix F · page {current.page} <ArrowUpRight size={14} />
              </a>
            </div>
            {current.note && <p className="source-review">{current.note}</p>}
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Property</th>
                    <th>Definition</th>
                    <th>Unit</th>
                    <th>Source value</th>
                  </tr>
                </thead>
                <tbody>
                  {current.properties.map((p) => (
                    <tr
                      key={p.symbol}
                      className={p.review ? "flagged-property" : ""}
                    >
                      <td>{p.symbol}</td>
                      <td>
                        {p.label}
                        {p.review && (
                          <small className="property-review">{p.review}</small>
                        )}
                      </td>
                      <td>{p.unit}</td>
                      <td>
                        {p.value && p.value !== "—" ? (
                          p.value
                        ) : (
                          <span className="unpublished">Not provided</span>
                        )}
                        {p.review && (
                          <span className="review-chip">Review</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="property-note">
              Values retain the appendix’s units and signs. Compression is
              printed negative; failure criteria use positive strength
              magnitudes. Blank entries remain missing.{" "}
              {current.family === "Sandwich cores"
                ? "Core thickness is the test thickness; other thicknesses are available according to the source."
                : "A listed ply thickness is specific to this source record."}
            </p>
            <div className="material-detail-footer">
              <button
                className="text-button"
                onClick={() =>
                  downloadFile(
                    `${current.id}-source.json`,
                    JSON.stringify(
                      {
                        source:
                          "Appendix F Material Properties (2026 v2), SE143AB, 1 February 2026",
                        status:
                          "Unqualified research reference; source review required before engineering use",
                        ...current,
                      },
                      null,
                      2,
                    ),
                    "application/json",
                  )
                }
              >
                <ArrowDownToLine size={14} /> Export source record
              </button>
              <Link
                className="button primary small"
                href={`/chat?material=${current.id}`}
              >
                Discuss this material <ArrowUpRight size={14} />
              </Link>
            </div>
          </article>
        </div>
      ) : (
        <div className="empty-library">
          <Search size={29} />
          <h3>No material records match.</h3>
          <p>Try a material name, manufacturing process, or another family.</p>
          <button
            className="button small"
            onClick={() => {
              setSearch("");
              setFamily("All families");
            }}
          >
            Reset filters
          </button>
        </div>
      )}
      <div className="library-source-note">
        <span className="tiny-label">A TRACEABLE STARTING POINT</span>
        <p>
          Transcribed from the supplied Appendix F, version 2, dated 1 February
          2026. These are research reference values, not qualified design
          allowables. The appendix describes periodic updates during coupon
          testing; nominal, dated, and incomplete records stay distinct. Amber
          markers identify source entries needing clarification.
        </p>
        <a href={materialSource} target="_blank" rel="noreferrer">
          Read the six-page source appendix <ArrowUpRight size={14} />
        </a>
      </div>
    </>
  );
}
