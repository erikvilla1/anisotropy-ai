"use client";
import { useEffect, useRef, useState } from "react";
import { Check, SlidersHorizontal, X } from "lucide-react";
import { Scope, scopeErrors, scopeQuestions } from "@/lib/demo";

export function ScopeEditor({
  scope,
  onSave,
}: {
  scope: Scope;
  onSave: (scope: Scope) => void;
}) {
  const modal = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState(scope);
  const [errors, setErrors] = useState<string[]>([]);
  const [isOpen, setOpen] = useState(false);
  useEffect(() => {
    if (!isOpen) return;
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = old;
    };
  }, [isOpen]);
  function close() {
    modal.current?.close();
    setOpen(false);
  }
  return (
    <>
      <button
        className="edit-scope-button"
        onClick={() => {
          setDraft(scope);
          setErrors([]);
          setOpen(true);
          modal.current?.showModal();
        }}
      >
        <SlidersHorizontal size={15} /> Edit specification{" "}
        <span>{scopeQuestions(scope).length} to define</span>
      </button>
      <dialog
        className="scope-dialog"
        ref={modal}
        onCancel={() => setOpen(false)}
        aria-labelledby="scope-editor-title"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const issues = scopeErrors(draft);
            setErrors(issues);
            if (!issues.length) {
              onSave(draft);
              close();
            }
          }}
        >
          <div className="lightbox-header">
            <div>
              <span className="tiny-label">ANALYSIS INPUTS / DRAFT</span>
              <h2 id="scope-editor-title">Define the specimen.</h2>
            </div>
            <button
              className="icon-button"
              type="button"
              aria-label="Close specification editor"
              onClick={close}
            >
              <X size={21} />
            </button>
          </div>
          <div className="scope-form-body">
            <p>
              Capture the inputs that will feed the engineering model. Blank
              fields remain open questions; no values are inferred.
            </p>
            <div className="scope-form-grid">
              <label>
                Test method
                <select
                  value={draft.test_standard || ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      test_standard: e.target.value || null,
                      hole_diameter_mm:
                        e.target.value === "ASTM D3039"
                          ? 0
                          : draft.hole_diameter_mm,
                    })
                  }
                >
                  <option value="">Not specified</option>
                  <option>ASTM D3039</option>
                  <option>ASTM D5766</option>
                </select>
              </label>
              <label>
                Material system
                <input
                  value={draft.material || ""}
                  placeholder="Material ID / approved record"
                  maxLength={200}
                  onChange={(e) =>
                    setDraft({ ...draft, material: e.target.value || null })
                  }
                />
              </label>
              {(
                [
                  ["length_mm", "Length (mm)"],
                  ["width_mm", "Width (mm)"],
                  ["thickness_mm", "Total thickness (mm)"],
                  ["hole_diameter_mm", "Hole diameter (mm)"],
                  ["applied_load_kN", "Applied tensile load (kN)"],
                  ["ply_count", "Ply count"],
                  ["safety_factor", "Factor of safety"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    type="number"
                    step={key === "ply_count" ? "1" : "any"}
                    value={draft[key] ?? ""}
                    placeholder="Not specified"
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        [key]:
                          e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                  />
                </label>
              ))}
              {(
                [
                  ["layup", "Ply stacking sequence", "e.g. [45/-45/0/90]2s"],
                  ["allowed_angles", "Allowed angles", "e.g. 0, ±45, 90"],
                  [
                    "boundary_conditions",
                    "Boundary conditions",
                    "Grip restraints and load introduction",
                  ],
                  [
                    "environment",
                    "Temperature & conditioning",
                    "e.g. room-temperature dry",
                  ],
                  [
                    "objective",
                    "Design objective",
                    "Minimize mass / maximize strength",
                  ],
                ] as const
              ).map(([key, label, placeholder]) => (
                <label key={key}>
                  {label}
                  <input
                    value={draft[key] || ""}
                    maxLength={300}
                    placeholder={placeholder}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        [key]:
                          e.target.value || (key === "objective" ? "" : null),
                      })
                    }
                  />
                </label>
              ))}
            </div>
            <div className="input-review-note">
              Before a real run: review units, property basis, ply ordering,
              symmetry/balance rules, mesh requirements, and any geometry
              outside the coupon MVP.
            </div>
            {!!errors.length && (
              <ul className="validation-errors" role="alert">
                {errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="scope-form-footer">
            <span>Draft inputs · no analysis results</span>
            <button className="button primary small" type="submit">
              Save draft <Check size={16} />
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
