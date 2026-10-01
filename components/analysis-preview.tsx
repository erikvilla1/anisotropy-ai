"use client";
import { useState } from "react";
import {
  ArrowDownToLine,
  Box,
  FileText,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { CouponVisual } from "./coupon-visual";
import { downloadFile, latexReport, Scope } from "@/lib/demo";

const outputModes = {
  geometry: {
    label: "CAD & mesh",
    heading: "A model you can inspect.",
    text: "The planned output includes parametric CAD, ply orientations, mesh, coordinate system, restraints, and applied loads. Geometry and boundary conditions stay tied to the input specification.",
    items: [
      "Parametric CAD / STEP",
      "Solver deck and mesh",
      "Ply orientations and boundary conditions",
    ],
  },
  stress: {
    label: "Stress",
    heading: "Follow the load through the laminate.",
    text: "Inspect stress components in global and ply coordinates. Identify concentrations, evaluate each applicable criterion, and compare multiple mesh densities before trusting a peak.",
    items: [
      "Per-ply stress tensors with units",
      "Convergence and CLT cross-checks",
      "Locations linked to elements and plies",
    ],
  },
  strain: {
    label: "Strain",
    heading: "Connect deformation to the test.",
    text: "Review the displacement and strain fields, then compare the modeled gauge region with the measurement method used in the lab. Record differences rather than hiding them.",
    items: [
      "Strain components and displacement",
      "Gauge-region comparison",
      "Assumptions and model limitations",
    ],
  },
  failure: {
    label: "Failure location",
    heading: "Understand where. Investigate why.",
    text: "The intended result brings together criterion-based critical regions, candidate failure modes, and learned patterns from observed fractures. Location and mode accuracy require independent physical validation.",
    items: [
      "Candidate critical ply and region",
      "Failure criterion and mode evidence",
      "Measured-versus-predicted location review",
    ],
  },
};

export function AnalysisPreview({ scope }: { scope: Scope }) {
  const [mode, setMode] = useState<keyof typeof outputModes>("failure");
  const [revised, setRevised] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const content = outputModes[mode];
  return (
    <section className="section analysis-section" id="deliverables">
      <div className="section-heading">
        <div>
          <span className="eyebrow">SERVICE 01 / THE INTENDED DELIVERABLE</span>
          <h2>
            See the result.
            <br />
            Inspect the reasoning.
          </h2>
        </div>
        <p>
          A preview of how geometry, fields, failure evidence, and scientific
          documentation will come together.
        </p>
      </div>
      <div className="output-workbench">
        <div className="output-toolbar">
          <span>
            <Box size={17} /> Analysis explorer
          </span>
          <span className="sample-badge">ILLUSTRATIVE · NOT SOLVED</span>
        </div>
        <div
          className="output-tabs"
          role="tablist"
          aria-label="Analysis output"
        >
          {Object.entries(outputModes).map(([key, value]) => (
            <button
              key={key}
              role="tab"
              id={`output-tab-${key}`}
              aria-selected={mode === key}
              aria-controls="output-panel"
              onClick={() => setMode(key as keyof typeof outputModes)}
            >
              {value.label}
            </button>
          ))}
        </div>
        <div
          className="output-grid"
          id="output-panel"
          role="tabpanel"
          aria-labelledby={`output-tab-${mode}`}
        >
          <div className="output-canvas">
            <div className="geometry-toggle">
              <button aria-pressed={!revised} onClick={() => setRevised(false)}>
                Baseline shape
              </button>
              <button aria-pressed={revised} onClick={() => setRevised(true)}>
                Revised shape
              </button>
            </div>
            <CouponVisual mode={mode} optimized={revised} />
            <div className="field-legend">
              <span>
                {mode === "geometry"
                  ? "GEOMETRY CONCEPT"
                  : "RELATIVE VISUAL SCALE"}
              </span>
              {mode !== "geometry" && (
                <>
                  <span className="legend-gradient" />
                  <span>Low → High</span>
                </>
              )}
            </div>
            <p>
              Concept artwork inspired by specimen-shape research. It does not
              depict your entered geometry or a computed field.
            </p>
          </div>
          <div className="output-explanation">
            <span className="tiny-label">
              {mode === "failure" ? "UNDERSTAND THE FAILURE" : "PLANNED OUTPUT"}
            </span>
            <h3>{content.heading}</h3>
            <p>{content.text}</p>
            <ul>
              {content.items.map((item) => (
                <li key={item}>
                  <ScanLine size={14} />
                  {item}
                </li>
              ))}
            </ul>
            <div className="pending-result">
              <ShieldCheck size={16} />
              <span>Analysis results not available in this preview</span>
            </div>
          </div>
        </div>
      </div>
      <div className="deliverable-grid">
        <article>
          <Box size={23} />
          <h3>The engineering package</h3>
          <p>
            Planned: CAD model, mesh, solver deck, fields, ply results, and a
            machine-readable input specification.
          </p>
          <button
            className="text-button"
            onClick={() =>
              downloadFile(
                "cad-definition-draft.json",
                JSON.stringify(
                  {
                    kind: "cad-definition-draft",
                    geometry: {
                      length_mm: scope.length_mm,
                      width_mm: scope.width_mm,
                      thickness_mm: scope.thickness_mm,
                      hole_diameter_mm: scope.hole_diameter_mm,
                    },
                    scope,
                    generated_cad: false,
                    solver_run: null,
                    planned_formats: ["STEP", "INP", "VTU", "CSV"],
                  },
                  null,
                  2,
                ),
                "application/json",
              )
            }
          >
            <ArrowDownToLine size={14} /> Download input definition
          </button>
          <small>Input draft only. Generated CAD/FEA files are not included.</small>
        </article>
        <article>
          <FileText size={23} />
          <h3>The scientific record</h3>
          <p>
            Document the physics, assumptions, methods, verification, and the
            evidence behind each conclusion.
          </p>
          <button
            className="text-button"
            aria-expanded={reportOpen}
            onClick={() => setReportOpen(!reportOpen)}
          >
            {reportOpen ? "Hide report outline" : "Preview report outline"}{" "}
            <FileText size={14} />
          </button>
          <small>LaTeX source template available below.</small>
        </article>
      </div>
      {reportOpen && (
        <div className="report-outline">
          <div>
            <span className="eyebrow">TRACEABILITY, BY DESIGN</span>
            <h3>Nothing arrives without its method.</h3>
            <p>
              This template contains your current draft inputs and placeholder
              sections. It contains no analysis results.
            </p>
            <button
              className="button primary small"
              onClick={() =>
                downloadFile(
                  "anisotropy-ai-report-outline.tex",
                  latexReport(scope),
                  "application/x-tex",
                )
              }
            >
              <ArrowDownToLine size={15} /> Download LaTeX outline
            </button>
          </div>
          <ol>
            {[
              "Problem definition & scope",
              "Material properties & source records",
              "Geometry, loads & boundary conditions",
              "Governing physics & failure criteria",
              "Mesh convergence & solver verification",
              "Stress, strain & failure assessment",
              "Physical test comparison & uncertainty",
              "Conclusions, limitations & provenance",
            ].map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
