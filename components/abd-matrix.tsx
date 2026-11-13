import { formatNumber } from "@/lib/number-format";

/** The A, B and D tables the calculator page and the home page share. Formatting changes precision for display only;
 * the engine supplies every value. The full page prints the site's one rule (`lib/number-format.ts`), four figures. */
export function formatted(value: number) {
  return formatNumber(value);
}

/** `focusable` gives the table's scroll box a tab stop, so a keyboard can scroll it; the home page's tour turns it off, since its
 * steps may stand out of turn, transparent, where a tab stop could not be seen. */
export function Matrix({ title, unit, meaning, values, compact = false, focusable = true }: {
  title: string; unit: string; meaning: string; values: number[][]; compact?: boolean; focusable?: boolean;
}) {
  return (
    <div className={compact ? "calc-matrix calc-matrix-compact" : "calc-matrix"}>
      <h3>{title} <span>{unit}</span></h3>
      {compact ? null : <p>{meaning}</p>}
      <div className="calc-table-scroll" tabIndex={focusable ? 0 : undefined} role={focusable ? "region" : undefined} aria-label={focusable ? `${title}, ${meaning.toLowerCase()} (${unit})` : undefined}>
        <table aria-label={`${title} matrix`}>
          <thead><tr><td />{["x", "y", "xy"].map((axis) => <th scope="col" key={axis}>{axis}</th>)}</tr></thead>
          <tbody>{values.map((row, i) => <tr key={i}><th scope="row">{["x", "y", "xy"][i]}</th>{row.map((value, j) => <td key={j}>{compact ? shortened(value) : formatted(value)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

/** The home page's small tables: the same rule at three significant figures, as its note says ("9.88 × 10⁷"), its spaces no-break so a
 * number stays on one line in a narrow cell. */
export function shortened(value: number) {
  return formatNumber(value, { figures: 3, zeros: false }).replace(/ /g, " ");
}
