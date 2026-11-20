"use client";

import type { WingVersion } from "@/lib/wing-versions";
import { StepPanel } from "./panels/step-panel";
import { useWing } from "./wing-context";

const SHOWN_CHANGES = 4;
const time = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};
const who = (v: WingVersion) => (v.by === "assistant" ? "the assistant" : "you");

/** The wing's History (ADR-0120, as the model tree's of ADR-0113): every version newest first, who made it and why, what it changed and
 * the check made from it; any version can be gone back to, which is kept as a new version. */
export function WingHistoryPanel() {
  const { versions } = useWing();
  const list = versions.list;
  const current = list[list.length - 1] ?? null;
  const before = list.length > 1 ? list[list.length - 2] : null;
  return (
    <StepPanel id="wing-history" step={11} title="History" open={false} note={current ? `version ${current.n}` : undefined}>
      {current ? (
        <div data-testid="wing-history">
          <div className="studio-buttons">
            <button type="button" className="studio-button" disabled={!before} onClick={() => before && versions.restore(before.n)} data-testid="wing-history-undo">
              Undo the last change</button>
          </div>
          <ol className="ws-history" reversed>
            {[...list].reverse().map((v) => (
              <li key={v.n} data-testid={`wing-version-${v.n}`} data-by={v.by}>
                <div className="ws-history-head">
                  <strong>Version {v.n}</strong>
                  <span className="ws-history-meta">{time(v.at)}, {who(v)}{v.why ? `: “${v.why}”` : ""}</span>
                  {v === current ? <span className="studio-badge" data-testid="wing-version-current">now</span>
                    : <button type="button" className="studio-text-button" onClick={() => versions.restore(v.n)} data-testid={`wing-restore-${v.n}`}>Go back to this</button>}
                </div>
                <ul className="ws-history-changes">
                  {v.changes.slice(0, SHOWN_CHANGES).map((c) => <li key={c}>{c}</li>)}
                  {v.changes.length > SHOWN_CHANGES ? <li>and {v.changes.length - SHOWN_CHANGES} more</li> : null}
                </ul>
                {v.check ? <p className="ws-history-run" data-testid={`wing-version-check-${v.n}`}>
                  {v.check.headline ? `Checked: ${v.check.headline}` : "Finite element check started from this version"}</p> : null}
              </li>
            ))}
          </ol>
        </div>
      ) : <p className="studio-hint">Each change to the wing is kept here once you make one.</p>}
    </StepPanel>
  );
}
