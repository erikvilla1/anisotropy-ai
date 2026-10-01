"use client";
import { MaterialBrowser } from "@/components/material-browser";
import { PhysicsBrowser } from "@/components/physics-browser";
import { useState } from "react";
import { ArrowUpRight, BookOpen, Database, Layers3 } from "lucide-react";

const stacks: Record<string, { angles: number[]; note: string }> = {
  "Balanced & symmetric": {
    angles: [45, -45, 0, 90, 90, 0, -45, 45],
    note: "An illustrative sequence mirrored about the midplane, with matched positive and negative off-axis plies. A design still needs its own constraints and verification.",
  },
  "Cross-ply": {
    angles: [0, 90, 0, 90, 90, 0, 90, 0],
    note: "An illustrative combination of longitudinal and transverse plies. Orientation alone does not establish strength or suitability for a load case.",
  },
  "Angle-ply": {
    angles: [45, -45, 45, -45, -45, 45, -45, 45],
    note: "An illustrative off-axis stack. The response depends on the material system, sequence, thickness, loading, and boundary conditions.",
  },
};
export default function Library() {
  const [tab, setTab] = useState("Materials");
  const [stack, setStack] = useState("Balanced & symmetric");
  return (
    <main id="main" className="inner-page">
      <section className="section page-intro">
        <span className="eyebrow">
          MATERIALS & PHYSICS / A FOUNDATION FOR RESEARCH
        </span>
        <div className="intro-grid">
          <div>
            <h1>
              Every layer has
              <br />
              <em>a source of truth.</em>
            </h1>
            <p>
              A place for material properties, laminate definitions, test
              context, and engineering methods—organized around the evidence
              that supports them.
            </p>
          </div>
          <div className="intro-aside">
            <BookOpen size={29} />
            <span>22 RECORDS · 6 SOURCE PAGES</span>
            <p>
              Materials, methods, and sources.
              <br />
              Explore the first collection.
              <br />
              Build understanding layer by layer.
            </p>
          </div>
        </div>
      </section>
      <section className="section library-section">
        <div
          className="library-tabs"
          role="tablist"
          aria-label="Library category"
        >
          {["Materials", "Layups & thickness", "Physics & references"].map(
            (t) => (
              <button
                key={t}
                role="tab"
                id={`library-tab-${t.split(" ")[0]}`}
                aria-controls="library-content"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
              >
                {t === "Materials" ? (
                  <Database size={16} />
                ) : t.startsWith("Layups") ? (
                  <Layers3 size={16} />
                ) : (
                  <BookOpen size={16} />
                )}{" "}
                {t}
              </button>
            ),
          )}
        </div>
        <div
          role="tabpanel"
          id="library-content"
          aria-labelledby={`library-tab-${tab.split(" ")[0]}`}
        >
          {tab === "Materials" && <MaterialBrowser />}
          {tab === "Layups & thickness" && (
            <div className="layup-library">
              <div className="layup-controls">
                <span className="eyebrow">ILLUSTRATIVE STACKS</span>
                <h2>
                  The sequence
                  <br />
                  is part of the design.
                </h2>
                <p>
                  Select a concept to inspect ply orientations. These examples
                  demonstrate the interface; they are not optimized or approved
                  designs.
                </p>
                <label>
                  Layup concept
                  <select
                    value={stack}
                    onChange={(e) => setStack(e.target.value)}
                  >
                    {Object.keys(stacks).map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <p>{stacks[stack].note}</p>
                <div className="thickness-note">
                  <span className="tiny-label">THICKNESS RECORD</span>
                  <strong>Measured, not assumed.</strong>
                  <p>
                    Source material records include available ply thicknesses.
                    This illustrative stack has no material assigned. A future
                    design record will link total laminate thickness,
                    manufacturing batch, and measurement method to the selected
                    material and specimen.
                  </p>
                </div>
              </div>
              <div className="stack-visual">
                <span className="tiny-label">TOP SURFACE → BOTTOM SURFACE</span>
                {stacks[stack].angles.map((angle, i) => (
                  <div
                    className="ply-layer"
                    key={`${stack}-${i}`}
                    style={{ "--angle": `${angle}deg` } as React.CSSProperties}
                  >
                    <span>PLY {String(i + 1).padStart(2, "0")}</span>
                    <div />
                    <strong>
                      {angle > 0 ? "+" : ""}
                      {angle}°
                    </strong>
                  </div>
                ))}
                <span className="stack-caption">
                  Orientation examples only · material properties not assigned
                </span>
              </div>
            </div>
          )}
          {tab === "Physics & references" && (
            <>
              <PhysicsBrowser />
              <div className="references-panel">
                <span className="eyebrow">RESEARCH READING</span>
                <h3>The questions have a context.</h3>
                <p>
                  Selected references from the supplied research slides. They
                  provide background on printed-polymer testing and processing,
                  not proof of the future composite model’s performance.
                </p>
                <a
                  href="https://doi.org/10.3390/cryst11080995"
                  target="_blank"
                  rel="noreferrer"
                >
                  Algarni & Ghazali · Mechanical properties and FDM process
                  parameters <ArrowUpRight size={15} />
                </a>
                <a
                  href="https://doi.org/10.1016/j.ijmecsci.2020.105767"
                  target="_blank"
                  rel="noreferrer"
                >
                  Huynh et al. · Epoxy-treated and as-printed polymeric
                  materials <ArrowUpRight size={15} />
                </a>
                <a
                  href="https://doi.org/10.1108/IJSI-03-2024-0040"
                  target="_blank"
                  rel="noreferrer"
                >
                  Delic et al. · FDM parameters, tensile strength, and fracture
                  occurrence <ArrowUpRight size={15} />
                </a>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
