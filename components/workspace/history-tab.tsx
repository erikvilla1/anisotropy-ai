"use client";

import { useState } from "react";
import { comparison, type ModelVersion } from "@/lib/model-versions";
import { useProject } from "@/components/studio/project-context";

const SHOWN_CHANGES = 4;
const time = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
};
const who = (v: ModelVersion) => (v.by === "assistant" ? "the assistant" : "you");

/** The History of the model tree (ADR-0113): every version of the setup, newest first, who made it and why, what it changed and the answer of
 * a run made from it; any version can be gone back to, which is kept as a new version, and two can be compared. */
export function HistoryTab() {
  const { versions } = useProject();
  const [picked, setPicked] = useState<number[]>([]);
  const list = versions.list;
  const current = list[list.length - 1] ?? null;
  const before = list.length > 1 ? list[list.length - 2] : null;
  const pair = picked.map((n) => list.find((v) => v.n === n)).filter((v): v is ModelVersion => v !== undefined);
  const compared = pair.length === 2 ? comparison(pair[0], pair[1]) : null;
  const pick = (n: number, on: boolean) => setPicked((p) => (on ? [...p.filter((x) => x !== n), n].slice(-2) : p.filter((x) => x !== n)));
  if (!current) return <p className="studio-hint">Each change to the setup is kept here.</p>;
  return (
    <div data-testid="tree-history">
      <div className="studio-buttons">
        <button type="button" className="studio-button" disabled={!before} onClick={() => before && versions.restore(before.n)} data-testid="history-undo">
          Undo the last change</button>
      </div>
      {compared ? (
        <div className="ws-history-compare" data-testid="history-compare">
          <p className="ws-tree-caption">Version {Math.min(pair[0].n, pair[1].n)} and version {Math.max(pair[0].n, pair[1].n)}</p>
          {compared.changes.length ? <ul className="ws-tree-lines">{compared.changes.map((c) => <li key={c}>{c}</li>)}</ul> : <p className="studio-hint">The same setup.</p>}
          <div className="studio-table-scroll">
            <table className="studio-table studio-table-prose">
              <thead><tr><th scope="col" /><th scope="col">Version {Math.min(pair[0].n, pair[1].n)}</th><th scope="col">Version {Math.max(pair[0].n, pair[1].n)}</th></tr></thead>
              <tbody>{compared.rows.map(([name, a, b]) => <tr key={name}><th scope="row">{name}</th><td>{a}</td><td>{b}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      ) : <p className="studio-hint">Tick two versions to compare their setups and their runs.</p>}
      <ol className="ws-history" reversed>
        {[...list].reverse().map((v) => (
          <li key={v.n} data-testid={`version-${v.n}`} data-by={v.by}>
            <div className="ws-history-head">
              <label className="ws-history-pick"><input type="checkbox" checked={picked.includes(v.n)} onChange={(e) => pick(v.n, e.target.checked)}
                aria-label={`Compare version ${v.n}`} /> <strong>Version {v.n}</strong></label>
              <span className="ws-history-meta">{time(v.at)}, {who(v)}{v.why ? `: “${v.why}”` : ""}</span>
              {v === current ? <span className="studio-badge" data-testid="version-current">now</span>
                : <button type="button" className="studio-text-button" onClick={() => versions.restore(v.n)} data-testid={`restore-${v.n}`}>Go back to this</button>}
            </div>
            <ul className="ws-history-changes">
              {v.changes.slice(0, SHOWN_CHANGES).map((c) => <li key={c}>{c}</li>)}
              {v.changes.length > SHOWN_CHANGES ? <li>and {v.changes.length - SHOWN_CHANGES} more</li> : null}
            </ul>
            {v.run ? <p className="ws-history-run" data-testid={`version-run-${v.n}`}>
              {v.run.result ? `Run: ${v.run.result.failure}, reaction ${v.run.result.reaction}, largest displacement ${v.run.result.displacement}` : "Run started from this version"}</p> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
