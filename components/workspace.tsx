"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUp,
  Check,
  CheckCircle2,
  Circle,
  FileSpreadsheet,
  FlaskConical,
  Layers3,
  Plus,
  RotateCcw,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import {
  Dataset,
  downloadFile,
  emptyScope,
  makeReply,
  parseDataset,
  Reply,
  sampleCSV,
  Scope,
  scopeQuestions,
  scopeErrors,
  latexReport,
} from "@/lib/demo";
import { ScopeEditor } from "./scope-editor";
import { curatedMaterials as materials } from "@/lib/curated-materials";
import { handoffKey } from "./home-composer";

const suggestions = [
  "Scope an open-hole tension coupon",
  "Compare D3039 and D5766",
  "What test data should I submit?",
];
function ScopeFields({ scope }: { scope: Scope }) {
  return (
    <dl className="scope-fields">
      {[
        ["Test method", scope.test_standard || "To be defined"],
        ["Material", scope.material || "To be confirmed"],
        [
          "Geometry",
          scope.length_mm || scope.width_mm
            ? `${scope.length_mm ?? "—"} × ${scope.width_mm ?? "—"} mm`
            : "Length × width needed",
        ],
        [
          "Applied load",
          scope.applied_load_kN
            ? `${scope.applied_load_kN} kN`
            : "To be defined",
        ],
        ["Safety factor", scope.safety_factor ?? "To be defined"],
        [
          "Thickness",
          scope.thickness_mm ? `${scope.thickness_mm} mm` : "To be defined",
        ],
        [
          "Hole diameter",
          scope.hole_diameter_mm !== null
            ? `${scope.hole_diameter_mm} mm`
            : "To be defined",
        ],
        [
          "Ply count / layup",
          `${scope.ply_count ?? "—"} / ${scope.layup ?? "To be defined"}`,
        ],
        ["Allowed angles", scope.allowed_angles || "To be defined"],
        ["Boundary conditions", scope.boundary_conditions || "To be defined"],
        ["Environment", scope.environment || "To be defined"],
      ].map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
function Answer({ reply }: { reply: Reply }) {
  if (reply.kind === "report")
    return (
      <>
        <h4>Document the physics behind the answer.</h4>
        <p>
          The intended report follows each conclusion back through its material
          record, boundary conditions, governing equations, mesh, solver checks,
          and physical-test evidence.
        </p>
        <ol className="report-chat-list">
          <li>Scope, geometry, layup, loads, and assumptions</li>
          <li>Material basis, constitutive equations, and failure criteria</li>
          <li>Mesh convergence and independent verification</li>
          <li>Stress, strain, critical regions, and failure-mode evidence</li>
          <li>Test comparison, uncertainty, limitations, and references</li>
        </ol>
        <button
          className="text-button"
          onClick={() =>
            downloadFile(
              "anisotropy-ai-report-outline.tex",
              latexReport(reply.scope),
              "application/x-tex",
            )
          }
        >
          <ArrowDownToLine size={14} /> Download LaTeX outline
        </button>
        <p className="answer-note">
          This download is a template with captured inputs. It contains no
          computed results or verified conclusions.
        </p>
      </>
    );
  if (reply.kind === "deliverables")
    return (
      <>
        <h4>From the model to the evidence.</h4>
        <p>
          The future analysis package will connect CAD geometry, a finite
          element model, stress and strain fields, and candidate failure
          locations with the physics that produced them.
        </p>
        <ul className="answer-checklist">
          {[
            "CAD geometry, mesh, ply orientations, and boundary conditions",
            "Per-ply stresses, strains, and criterion-based margins",
            "Critical regions and possible failure modes, checked against lab observations",
            "A LaTeX/PDF record of assumptions, verification, and provenance",
          ].map((x) => (
            <li key={x}>
              <Check size={15} />
              {x}
            </li>
          ))}
        </ul>
        <p className="answer-note">
          This preview cannot determine where your coupon fails. The response
          outlines the planned analysis package.
        </p>
        <div className="next-question">
          <span className="tiny-label">INPUTS TO RESOLVE NEXT</span>
          <p>
            {scopeQuestions(reply.scope)[0] ||
              "Review the material basis, modeling assumptions, and mesh plan before analysis."}
          </p>
        </div>
      </>
    );
  if (reply.kind === "table")
    return (
      <>
        <h4>Two tests. Different questions.</h4>
        <p>These are the two coupon types in the first-phase project scope.</p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Test</th>
                <th>D3039</th>
                <th>D5766</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Coupon</td>
                <td>Unnotched</td>
                <td>Open-hole</td>
              </tr>
              <tr>
                <td>Focus</td>
                <td>Tensile properties</td>
                <td>Notched tensile strength</td>
              </tr>
              <tr>
                <td>Geometry</td>
                <td>Flat laminate</td>
                <td>Laminate with a central hole</td>
              </tr>
              <tr>
                <td>Planned analysis</td>
                <td>CLT + FEA</td>
                <td>Open-hole model + FEA</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="answer-note">
          Select a test method before defining geometry and loads. Test setup
          and dimensions require engineering review.
        </p>
      </>
    );
  if (reply.kind === "json")
    return (
      <>
        <h4>Your scope, structured.</h4>
        <p>Only inputs captured in this conversation are populated.</p>
        <pre>{JSON.stringify(reply.scope, null, 2)}</pre>
        <button
          className="text-button"
          onClick={() =>
            downloadFile(
              "anisotropy-ai-scope.json",
              JSON.stringify(reply.scope, null, 2),
              "application/json",
            )
          }
        >
          <ArrowDownToLine size={14} /> Download scope JSON
        </button>
      </>
    );
  if (reply.kind === "checklist")
    return (
      <>
        <h4>Build a traceable test record.</h4>
        <p>
          Start with one row per coupon. The sample CSV includes the fields this
          preview checks.
        </p>
        <ul className="answer-checklist">
          {[
            "Identify the coupon, source panel, and material system.",
            "Record the standard, layup, ply count, and dimensions.",
            "Include measured failure load, stress, modulus, and failure mode.",
            "Review missing fields and invalid rows before submission.",
            "Keep every specimen linked to its source panel and test conditions.",
          ].map((t) => (
            <li key={t}>
              <Check size={15} />
              {t}
            </li>
          ))}
        </ul>
        <p className="answer-note">
          Keep provenance, test conditions, and review notes with each specimen.
          Files in this preview stay in your browser.
        </p>
      </>
    );
  if (reply.kind === "overview")
    return (
      <>
        <h4>From a coupon specification to a traceable result.</h4>
        <p>
          Anisotropy AI is a proposed engineering workflow for composite
          laminates. The first phase focuses on unnotched and open-hole tension
          coupons in one carbon/epoxy material system.
        </p>
        <div className="mini-pipeline">
          <span>Define</span>
          <ArrowRight size={14} />
          <span>Analyze</span>
          <ArrowRight size={14} />
          <span>Test</span>
          <ArrowRight size={14} />
          <span>Learn</span>
        </div>
        <p>
          Define your requirements, explore material choices, and follow the
          physics behind each conclusion. Independent coupon testing supports
          the research before it extends to larger structures.
        </p>
      </>
    );
  return (
    <>
      <h4>Let’s define the engineering question.</h4>
      <p>
        I’ve captured the supported inputs from your request. This draft is a
        starting point for review.
      </p>
      <ScopeFields scope={reply.scope} />
      {scopeErrors(reply.scope).length > 0 && (
        <ul className="validation-errors" role="alert">
          {scopeErrors(reply.scope).map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      )}
      <div className="next-question">
        <span className="tiny-label">NEXT TO DEFINE</span>
        <p>
          {scopeQuestions(reply.scope)[0] ||
            "Draft inputs captured. Next, review property sources, design rules, and mesh settings with the engineering team."}
        </p>
      </div>
      <p className="answer-note">
        This scope is a draft. It does not include calculated layups, failure
        loads, or margins.
      </p>
    </>
  );
}

export function Workspace({
  activeTab,
  setActiveTab,
  onScopeChange,
  standalone = false,
  chatOnly = false,
}: {
  activeTab: "assistant" | "data";
  setActiveTab: (v: "assistant" | "data") => void;
  onScopeChange?: (scope: Scope) => void;
  standalone?: boolean;
  chatOnly?: boolean;
}) {
  const [input, setInput] = useState("");
  const [scope, setScope] = useState<Scope>(emptyScope);
  const [messages, setMessages] = useState<{ prompt: string; reply: Reply }[]>(
    [],
  );
  const [format, setFormat] = useState("auto");
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [reading, setReading] = useState(false);
  const [fileError, setFileError] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const chatBody = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);
  useEffect(() => {
    onScopeChange?.(scope);
  }, [scope, onScopeChange]);
  useEffect(() => {
    if (initialized.current || activeTab !== "assistant") return;
    initialized.current = true;
    const params = new URLSearchParams(window.location.search);
    const record = materials.find((m) => m.id === params.get("material"));
    const initial = record
      ? {
          ...emptyScope,
          material: record.name,
        }
      : emptyScope;
    let handoff: { prompt?: string; format?: string } | null = null;
    try {
      const stored = sessionStorage.getItem(handoffKey);
      if (stored) {
        handoff = JSON.parse(stored);
        sessionStorage.removeItem(handoffKey);
      }
    } catch {
      /* Storage can be unavailable; query fallback below remains usable. */
    }
    if (!handoff && params.get("prompt"))
      handoff = {
        prompt: params.get("prompt")!,
        format: params.get("format") || "auto",
      };
    if (typeof handoff?.prompt === "string" && handoff.prompt.trim()) {
      const prompt = handoff.prompt.trim().slice(0, 4000);
      const reply = makeReply(prompt, initial);
      const chosen = [
        "brief",
        "table",
        "checklist",
        "json",
        "deliverables",
        "report",
      ].includes(handoff.format || "")
        ? handoff.format!
        : "auto";
      if (chosen !== "auto") reply.kind = chosen as Reply["kind"];
      setFormat(chosen);
      setScope(reply.scope);
      setMessages([{ prompt, reply }]);
      if (params.has("prompt")) window.history.replaceState(null, "", "/chat");
    } else if (record) setScope(initial);
    const material = new URLSearchParams(window.location.search).get(
      "material",
    );
    const systems: Record<string, string> = {
      "carbon-epoxy": "Carbon / epoxy — material system to confirm",
      "glass-epoxy": "Glass / epoxy — future material system",
      "aramid-epoxy": "Aramid / epoxy — future material system",
      "carbon-thermoplastic": "Carbon / thermoplastic — future material system",
      "printed-polymer":
        "Printed polymer — research context, outside laminate MVP",
    };
    if (material && systems[material])
      setScope((s) => ({ ...s, material: systems[material] }));
  }, []);
  useEffect(() => {
    if (messages.length)
      chatBody.current?.scrollTo({
        top: chatBody.current.scrollHeight,
        behavior: "smooth",
      });
  }, [messages]);
  function send(value = input) {
    const prompt = value.trim();
    if (!prompt) return;
    const reply = makeReply(prompt, scope);
    if (format !== "auto") reply.kind = format as Reply["kind"];
    setScope(reply.scope);
    setMessages((m) => [...m, { prompt, reply }]);
    setInput("");
  }
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
      setFileError("Please use a CSV smaller than 5 MB for this preview.");
      return;
    }
    setReading(true);
    try {
      setDataset(parseDataset(await file.text(), file.name));
    } catch {
      setFileError("This file could not be read. Please try another CSV.");
    } finally {
      setReading(false);
    }
  }
  const ready = dataset && dataset.errors.length === 0;
  return (
    <section
      className={`section workspace-section ${standalone ? "standalone-workspace" : ""}`}
      id="workspace"
    >
      {!standalone && (
        <div className="section-heading">
          <div>
            <span className="eyebrow">03 / EXPLORE THE EXPERIENCE</span>
            <h2>
              A question is
              <br />a good place to start.
            </h2>
          </div>
          <p>
            Define the scope. Bring in the evidence.
            <br />
            See how the pieces will come together.
          </p>
        </div>
      )}
      <div className="workspace">
        {!chatOnly && (
          <div className="workspace-top">
            {standalone ? (
              <span className="studio-mode">
                {activeTab === "assistant"
                  ? "ENGINEERING CONVERSATION"
                  : "TEST-DATA SUBMISSION"}
              </span>
            ) : (
              <div
                className="workspace-tabs"
                role="tablist"
                aria-label="Demo workspace"
              >
                <button
                  role="tab"
                  aria-selected={activeTab === "assistant"}
                  aria-controls="assistant-panel"
                  id="assistant-tab"
                  className={activeTab === "assistant" ? "active" : ""}
                  onClick={() => setActiveTab("assistant")}
                >
                  <Sparkles size={16} /> AI scope assistant
                </button>
                <button
                  role="tab"
                  aria-selected={activeTab === "data"}
                  aria-controls="data-panel"
                  id="data-tab"
                  className={activeTab === "data" ? "active" : ""}
                  onClick={() => setActiveTab("data")}
                >
                  <FileSpreadsheet size={16} /> Test data
                </button>
              </div>
            )}
            <span className="preview-label">
              <span /> INTERACTIVE PREVIEW
            </span>
          </div>
        )}
        <div
          id="assistant-panel"
          role={standalone ? "region" : "tabpanel"}
          aria-label={standalone ? "Engineering conversation" : undefined}
          aria-labelledby={standalone ? undefined : "assistant-tab"}
          hidden={activeTab !== "assistant"}
        >
          <div className="assistant-grid">
            {!chatOnly && (
              <aside className="assistant-sidebar">
                <div className="assistant-title">
                  <div className="assistant-symbol">
                    <Layers3 size={24} />
                  </div>
                  <h3>
                    Your engineering
                    <br />
                    question, made clear.
                  </h3>
                  <p>Turn an idea into a scope your team can build on.</p>
                </div>
                <div className="sidebar-detail">
                  <span className="tiny-label">IN THIS CONVERSATION</span>
                  <div>
                    <Circle size={13} /> Coupon specification
                  </div>
                  <div>
                    <Circle size={13} /> Test requirements
                  </div>
                  <div>
                    <Circle size={13} /> Structured deliverables
                  </div>
                </div>
                <div className="sidebar-bottom">
                  <span className="status-dot" /> Guided conversation preview
                </div>
              </aside>
            )}
            <div className="chat">
              <div className="scope-editor-row">
                <ScopeEditor
                  scope={scope}
                  onSave={(next) => {
                    setScope(next);
                    setMessages((m) => [
                      ...m,
                      {
                        prompt: "Updated the specimen specification.",
                        reply: {
                          kind: "brief",
                          scope: next,
                          prompt: "Review updated inputs",
                        },
                      },
                    ]);
                  }}
                />
              </div>
              <div className="chat-toolbar">
                <span>
                  <span className="status-dot" /> Anisotropy AI{" "}
                  <span className="muted">/ Chat</span>
                </span>
                <button
                  className="icon-button"
                  aria-label="Reset conversation"
                  title="Reset conversation"
                  onClick={() => {
                    setMessages([]);
                    setScope(emptyScope);
                    setInput("");
                    setFormat("auto");
                  }}
                >
                  <RotateCcw size={15} />
                </button>
              </div>
              <div
                className="chat-body"
                ref={chatBody}
                aria-live="polite"
                aria-relevant="additions"
              >
                <div className="assistant-message">
                  <span className="message-avatar">
                    <Sparkles size={15} />
                  </span>
                  <div>
                    <span className="message-author">
                      ANISOTROPY AI <small>DEMO</small>
                    </span>
                    <h4>What are you working toward?</h4>
                    <p>
                      Tell me about the loads, geometry, material, or ply layup.
                      I’ll collect the missing inputs and organize the planned
                      CAD, FEA, failure assessment, and report package.
                    </p>
                    <div className="prompt-suggestions">
                      {suggestions.map((s, i) => (
                        <button key={s} onClick={() => send(s)}>
                          {
                            [
                              <Layers3 size={14} key="l" />,
                              <FlaskConical size={14} key="f" />,
                              <FileSpreadsheet size={14} key="d" />,
                            ][i]
                          }
                          {s}
                          <ArrowUp size={13} />
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                {messages.map((m, i) => (
                  <div className="conversation-turn" key={i}>
                    <div className="user-message">{m.prompt}</div>
                    <div className="assistant-message">
                      <span className="message-avatar">
                        <Sparkles size={15} />
                      </span>
                      <div>
                        <span className="message-author">
                          ANISOTROPY AI{" "}
                          <small>{m.reply.kind.toUpperCase()}</small>
                        </span>
                        <Answer reply={m.reply} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <form
                className="chat-composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  send();
                }}
              >
                <textarea
                  aria-label="Message the scope assistant"
                  placeholder="Describe a coupon, ask a question, or define your scope…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  maxLength={4000}
                  rows={2}
                  onKeyDown={(e) => {
                    if (
                      e.key === "Enter" &&
                      !e.shiftKey &&
                      !e.nativeEvent.isComposing
                    ) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <div className="composer-footer">
                  <label>
                    Response{" "}
                    <select
                      aria-label="Response format"
                      value={format}
                      onChange={(e) => setFormat(e.target.value)}
                    >
                      <option value="auto">Automatic</option>
                      <option value="brief">Scope brief</option>
                      <option value="table">Comparison table</option>
                      <option value="checklist">Data checklist</option>
                      <option value="json">Structured JSON</option>
                      <option value="deliverables">Analysis package</option>
                      <option value="report">LaTeX report outline</option>
                    </select>
                  </label>
                  <button
                    className="send-button"
                    type="submit"
                    disabled={!input.trim()}
                    aria-label="Send message"
                  >
                    <ArrowUp size={20} />
                  </button>
                </div>
              </form>
              <p className="chat-disclaimer">
                Guided scope preview. No analysis results are calculated.
              </p>
            </div>
          </div>
        </div>
        {!chatOnly && (
          <div
            id="data-panel"
            role={standalone ? "region" : "tabpanel"}
            aria-label={standalone ? "Test-data submission" : undefined}
            aria-labelledby={standalone ? undefined : "data-tab"}
            hidden={activeTab !== "data"}
          >
            <div className="data-layout">
              <div className="data-intro">
                <span className="tiny-label">THE LAB LOOP STARTS HERE</span>
                <h3>
                  Every coupon
                  <br />
                  adds evidence.
                </h3>
                <p>
                  Bring measured results into a consistent format, then review
                  them before they become part of the data foundation.
                </p>
                <ol className="data-steps">
                  <li className="done">
                    <Check size={15} />
                    <span>Choose a test dataset</span>
                  </li>
                  <li className={dataset ? "done" : ""}>
                    <span className="step-marker">2</span>
                    <span>Validate and review</span>
                  </li>
                  <li className={submitted ? "done" : ""}>
                    <span className="step-marker">3</span>
                    <span>Submit for review</span>
                  </li>
                </ol>
                <p className="local-note">
                  Files stay in this browser session. This demo does not upload,
                  train, or run an analysis.
                </p>
              </div>
              <div className="data-main">
                <input
                  ref={fileInput}
                  aria-label="Upload test CSV"
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
                            {dataset.rows.length} records ·{" "}
                            {dataset.example
                              ? "Illustrative data, not lab measurements"
                              : "Local file preview"}
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
                            ? "Preview schema checks passed"
                            : `${dataset.errors.length} validation issues to review`}
                        </strong>
                        <span>
                          {ready
                            ? "Required fields, numeric values, IDs, and coupon geometry checked."
                            : "Correct the source CSV and upload it again before submitting."}
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
                        <thead>
                          <tr>
                            <th>Coupon ID</th>
                            <th>Standard</th>
                            <th>Load (kN)</th>
                            <th>Stress (MPa)</th>
                            <th>Mode</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dataset.rows.slice(0, 8).map((r, i) => (
                            <tr key={i}>
                              <td>{r.coupon_id || "—"}</td>
                              <td>{r.test_standard || "—"}</td>
                              <td>{r.failure_load_kN || "—"}</td>
                              <td>{r.failure_stress_MPa || "—"}</td>
                              <td>{r.failure_mode || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {dataset.rows.length > 8 && (
                      <p className="muted">
                        Showing the first 8 of {dataset.rows.length} records.
                      </p>
                    )}
                    {submitted ? (
                      <div className="submission-result" role="status">
                        <CheckCircle2 size={23} />
                        <div>
                          <h4>Submission preview complete.</h4>
                          <p>
                            {dataset.rows.length} records staged for engineering
                            review in this session. No records were sent to a
                            server.
                          </p>
                          <button
                            className="text-button"
                            onClick={() =>
                              downloadFile(
                                "submission-preview.json",
                                JSON.stringify(
                                  {
                                    status: "local-preview-only",
                                    illustrative: dataset.example,
                                    file: dataset.name,
                                    records: dataset.rows,
                                  },
                                  null,
                                  2,
                                ),
                                "application/json",
                              )
                            }
                          >
                            <ArrowDownToLine size={14} /> Download review
                            package
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="submission-actions">
                        <span>
                          Keep the review record with the source test evidence.
                        </span>
                        <button
                          className="button primary small"
                          disabled={!ready}
                          onClick={() => setSubmitted(true)}
                        >
                          Preview submission <ArrowRight size={15} />
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
