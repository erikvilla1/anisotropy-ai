"use client";

import { sweepHeading, sweepTable, type RepairSweepAnswer } from "@/lib/repair-chat";

/** What the engineer may do with what the repair's chat worked: whether it is applied or not, the repair it was worked on changed since,
 * the page's repair is the one it gives, and the taps. */
export type Worked = { outcome?: "applied" | "dismissed" | "undone"; stale: boolean; current: boolean; onApply(): void; onDismiss(): void; onUndo(): void };

/** What the engineer may do with a preview or a pick: apply it or not; once applied, undo it while the repair is still the one applied. */
export function Outcome({ outcome, stale, current, pick, onApply, onDismiss, onUndo }: Worked & { pick?: boolean }) {
  if (outcome === "applied") {
    return (
      <p className="chat-note" data-testid="repair-applied">Applied: the repair is worked again.{" "}
        {current ? <button type="button" className="studio-text-button" onClick={onUndo} data-testid="repair-undo">Undo</button> : "It has changed since."}</p>
    );
  }
  if (outcome === "undone") return <p className="chat-note" data-testid="repair-undone">Undone: the repair is as it was.</p>;
  if (outcome === "dismissed") return null;
  if (stale) return <p className="chat-note">The repair changed after this was worked: ask again to work it on the repair as it stands.</p>;
  return (
    <div className="chat-actions">
      <button type="button" className="studio-button" onClick={onApply} data-testid="repair-apply">{pick ? "Apply the pick" : "Apply"}</button>
      <button type="button" className="studio-text-button" onClick={onDismiss}>Dismiss</button>
    </div>
  );
}

/** A sweep of the repair (ADR-0136): the answer first, in a sentence or two, the pick's check when its slice was solved, the cautions,
 * and the values with what could not be worked folded under them. The chat's sweep offers its pick (`worked`); a plan's sweep has its
 * pick taken by the plan's own step (ADR-0144, step 5), so it offers nothing. */
export function Sweep({ sweep, worked }: { sweep: RepairSweepAnswer; worked?: Worked }) {
  const table = sweepTable(sweep);
  const rest = sweep.words.filter((line) => !sweep.answer.includes(line));
  return (
    <div data-testid="repair-sweep">
      <h4 data-testid="repair-sweep-heading">{sweepHeading(sweep)}</h4>
      {sweep.answer.map((line) => <p key={line} data-testid="repair-sweep-words">{line}</p>)}
      {sweep.check ? <p data-testid="repair-sweep-check" data-holds={sweep.check.close ? "close" : sweep.check.holds === null ? "unchecked" : String(sweep.check.holds)}>{sweep.check.words.join(" ")}</p> : null}
      {sweep.cautions.map((line) => <p key={line} className="chat-note" data-testid="repair-sweep-caution">{line}</p>)}
      <details className="chat-details" open={sweep.answer.length === 0 ? true : undefined}>
        <summary>Details: the {table.rows.length} values</summary>
        {rest.map((line) => <p key={line} className="chat-note" data-testid="repair-sweep-rest">{line}</p>)}
        <div className="studio-table-scroll">
          <table className="studio-table studio-table-num studio-table-compact" data-testid="repair-sweep-table">
            <thead><tr>{table.head.map((h, i) => <th key={h} scope="col" className={i ? "studio-num-head" : undefined}>{h}</th>)}</tr></thead>
            <tbody>{table.rows.map((row) => (
              <tr key={row.cells[0]} data-pick={row.pick ? "true" : undefined} data-current={row.current ? "true" : undefined}>
                <th scope="row" className="studio-text-cell">{row.cells[0]}{row.pick ? " (pick)" : row.current ? " (as it is)" : ""}</th>
                {row.refused !== null
                  ? <td className="studio-text-cell" colSpan={table.head.length - 1}>Not worked: {row.refused}</td>
                  : row.cells.slice(1).map((cell, i) => <td key={`${table.head[i + 1]}`} className="studio-num">{cell}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
      </details>
      {sweep.pick !== null && worked ? <Outcome {...worked} pick /> : null}
    </div>
  );
}
