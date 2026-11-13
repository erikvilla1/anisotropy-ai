"use client";

import { useRef, useState } from "react";
import {
  ArrowDownToLine,
  Check,
  CheckCircle2,
  Circle,
  FileSpreadsheet,
  Plus,
  Upload,
  X,
} from "lucide-react";
import { Dataset, downloadFile, parseDataset, sampleCSV } from "@/lib/demo";

/** The test-data page's panel: choose a CSV of coupon results, check it in the browser and download the checked records.
 * Nothing is uploaded. */
export function DataWorkspace() {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [reading, setReading] = useState(false);
  const [fileError, setFileError] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  async function loadFile(file?: File) {
    if (!file) return;
    setFileError("");
    setSubmitted(false);
    setDataset(null);
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setFileError(
        "Choose a CSV file. Download the template below to see the expected columns.",
      );
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setFileError("Choose a CSV smaller than 5 MB.");
      return;
    }
    setReading(true);
    try {
      setDataset(parseDataset(await file.text(), file.name));
    } catch {
      setFileError("This file could not be read. Check that it is a CSV with the template's columns, then choose it again.");
    } finally {
      setReading(false);
    }
  }
  const ready = dataset && dataset.errors.length === 0;
  return (
    <section className="section workspace-section standalone-workspace data-workspace" id="workspace">
      <div className="workspace">
        <div className="workspace-top">
          <span className="studio-mode">CHECK A CSV</span>
        </div>
        <div id="data-panel" role="region" aria-label="Test data">
          <div className="data-layout">
            <div className="data-intro">
              <h2>
                Every coupon{" "}
                <br />
                adds evidence.
              </h2>
              <p>
                Put measured coupon results in one format and check them
                before review.
              </p>
              <ol className="data-steps">
                {[
                  { label: "Choose a test file", done: !!dataset },
                  { label: "Check the results", done: !!ready },
                  { label: "Download checked records", done: submitted },
                ].map((step, i, steps) => {
                  const active = !step.done && steps.slice(0, i).every((s) => s.done);
                  return (
                    <li
                      key={step.label}
                      className={step.done ? "done" : ""}
                      aria-current={active ? "step" : undefined}
                    >
                      {step.done ? (
                        <Check size={15} />
                      ) : (
                        <span className="step-marker">{i + 1}</span>
                      )}
                      <span>
                        {step.label}
                        {step.done && (
                          <span className="sr-only"> (completed)</span>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ol>
              <p className="local-note">
                Your file is checked in this browser. Nothing is uploaded.
              </p>
            </div>
            <div className="data-main">
              <input
                ref={fileInput}
                aria-label="Choose a test CSV"
                type="file"
                accept=".csv,text/csv"
                hidden
                onChange={(e) => {
                  loadFile(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              {!dataset && (
                <>
                  <button
                    className={`dropzone ${dragging ? "dragging" : ""}`}
                    disabled={reading}
                    onClick={() => fileInput.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragging(true);
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragging(false);
                      loadFile(e.dataTransfer.files[0]);
                    }}
                  >
                    <span className="upload-icon">
                      <Upload size={25} />
                    </span>
                    <strong>
                      {reading
                        ? "Reading your file…"
                        : "Drop your test data here"}
                    </strong>
                    <span>or click to choose a file</span>
                    <small>CSV · up to 5 MB · 5,000 coupons</small>
                  </button>
                  <div className="data-options">
                    <button
                      className="text-button"
                      onClick={() => {
                        setDataset(
                          parseDataset(
                            sampleCSV,
                            "example-coupons.csv",
                            true,
                          ),
                        );
                        setFileError("");
                      }}
                    >
                      <Plus size={15} /> Load example data
                    </button>
                    <button
                      className="text-button"
                      onClick={() =>
                        downloadFile(
                          "coupon-template.csv",
                          sampleCSV.split("\n")[0] + "\n",
                          "text/csv",
                        )
                      }
                    >
                      <ArrowDownToLine size={15} /> CSV template
                    </button>
                  </div>
                </>
              )}
              {fileError && (
                <p className="error-banner" role="alert">
                  {fileError}
                </p>
              )}
              {dataset && (
                <>
                  <div className="dataset-heading">
                    <div>
                      <FileSpreadsheet size={20} />
                      <span>
                        <strong>{dataset.name}</strong>
                        <small>
                          {dataset.rows.length}{" "}
                          {dataset.rows.length === 1 ? "coupon" : "coupons"} ·{" "}
                          {dataset.example
                            ? "Illustrative data, not lab measurements"
                            : "Checked in this browser"}
                        </small>
                      </span>
                    </div>
                    <button
                      className="icon-button"
                      aria-label="Remove dataset"
                      onClick={() => {
                        setDataset(null);
                        setSubmitted(false);
                      }}
                    >
                      <X size={17} />
                    </button>
                  </div>
                  <div
                    className={`validation-banner ${ready ? "valid" : "invalid"}`}
                    role="status"
                  >
                    {ready ? (
                      <CheckCircle2 size={18} />
                    ) : (
                      <Circle size={18} />
                    )}
                    <div>
                      <strong>
                        {ready
                          ? "File checked: ready for review."
                          : `${dataset.errors.length} ${dataset.errors.length === 1 ? "issue" : "issues"} to fix`}
                      </strong>
                      <span>
                        {ready
                          ? "Required fields, numeric values, IDs, and coupon geometry checked."
                          : "Correct the CSV and choose it again."}
                      </span>
                    </div>
                  </div>
                  {!!dataset.errors.length && (
                    <ul className="validation-errors">
                      {dataset.errors.slice(0, 12).map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                      {dataset.errors.length > 12 && (
                        <li>
                          …and {dataset.errors.length - 12} more issues.
                        </li>
                      )}
                    </ul>
                  )}
                  <div className="table-scroll">
                    <table className="data-table">
                      <caption className="sr-only">
                        {dataset.name}: first coupons
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">Coupon ID</th>
                          <th scope="col">Standard</th>
                          <th scope="col" className="numeric">Load (kN)</th>
                          <th scope="col" className="numeric">Stress (MPa)</th>
                          <th scope="col">Mode</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dataset.rows.slice(0, 8).map((r, i) => (
                          <tr key={i}>
                            <th scope="row">{r.coupon_id || "—"}</th>
                            <td>{r.test_standard || "—"}</td>
                            <td className="numeric">{r.failure_load_kN || "—"}</td>
                            <td className="numeric">{r.failure_stress_MPa || "—"}</td>
                            <td>{r.failure_mode || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {dataset.rows.length > 8 && (
                    <p className="muted">
                      Showing the first 8 of {dataset.rows.length} coupons.
                    </p>
                  )}
                  <div className="submission-actions">
                    <span role="status">
                      {submitted
                        ? "Checked records downloaded. Keep them with the source test evidence."
                        : "Keep the checked records with the source test evidence."}
                    </span>
                    <button
                      className="button primary small"
                      disabled={!ready}
                      onClick={() => {
                        downloadFile(
                          `${dataset.name.replace(/\.csv$/i, "")}-checked.json`,
                          JSON.stringify(
                            {
                              status: "checked",
                              illustrative: dataset.example,
                              file: dataset.name,
                              records: dataset.rows,
                            },
                            null,
                            2,
                          ),
                          "application/json",
                        );
                        setSubmitted(true);
                      }}
                    >
                      <ArrowDownToLine size={15} /> Download checked records
                      (JSON)
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
