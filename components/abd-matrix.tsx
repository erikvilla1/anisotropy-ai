import { formatNumber } from "@/lib/number-format";

/** The A, B and D tables the calculator page and the home page share. Formatting changes precision for display only;
 * the engine supplies every value. The full page prints the site's one rule (`lib/number-format.ts`), four figures. */
export function formatted(value: number) {
  return formatNumber(value);
}

export function Matrix({ title, unit, meaning, values, compact = false }: {
  title: string; unit: string; meaning: string; values: number[][]; compact?: boolean;
}) {
  return (
    <div className={compact ? "calc-matrix calc-matrix-compact" : "calc-matrix"}>
      <h3>{title} <span>{unit}</span></h3>
      {compact ? null : <p>{meaning}</p>}
      <div className="calc-table-scroll" tabIndex={0} role="region" aria-label={`${title}, ${meaning.toLowerCase()} (${unit})`}>
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
