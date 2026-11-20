"use client";

import { useMemo } from "react";
import katex from "katex";
// KaTeX and its stylesheet load with this component alone, which the chat brings in only when a working is shown (ADR-0103).
import "katex/dist/katex.min.css";
import type { WorkingChain } from "@/lib/studio-api";
import { givenText } from "@/lib/result-working";
import { shownSentence } from "@/lib/studio-copy";

/** A formula as typeset markup; one the typesetter cannot read is shown as it was written, never dropped. Set in line, with full-size
 * fractions, so a long line breaks at its own operators in a narrow chat and its result is never off the edge. */
function typeset(expression: string): string {
  return katex.renderToString(expression.replaceAll("\\frac", "\\dfrac"), { displayMode: false, output: "htmlAndMathml", throwOnError: false, strict: "ignore", trust: false });
}

function Formula({ expression, block = true }: { expression: string; block?: boolean }) {
  const html = useMemo(() => typeset(expression), [expression]);
  return block ? <div className="chat-working-formula" dangerouslySetInnerHTML={{ __html: html }} /> : <span dangerouslySetInnerHTML={{ __html: html }} />;
}

/** The working behind an answer (ADR-0103): each step with what it rests on, the values put in, its formula and the formula with the
 * values in place. Every number and formula is the package's; this component typesets them and prints the values by the page's rule. */
export function WorkingSteps({ chain, figures, titled = true }: { chain: WorkingChain; figures: number; titled?: boolean }) {
  return (
    <ol className="chat-working-steps">
      {chain.steps.map((step) => (
        <li key={step.id} data-testid="chat-working-step" data-step={step.id}>
          {titled ? <h5>{step.title}</h5> : null}
          <p data-testid="chat-working-text">{shownSentence(step.text)}</p>
          {step.given.length ? (
            <table className="studio-table studio-table-compact chat-working-given">
              <tbody>{step.given.map((row) => (
                <tr key={row.symbol}><th scope="row"><Formula expression={row.symbol} block={false} /></th>
                  <td data-testid="chat-working-value">{givenText(row.value, figures)}{row.unit !== "-" ? ` ${row.unit}` : ""}</td><td className="studio-text-cell">{row.what}</td></tr>
              ))}</tbody>
            </table>
          ) : null}
          {step.equations.map((equation, i) => (
            <div key={i} className="chat-working-equation" data-testid="chat-working-equation">
              {equation.formula ? <Formula expression={equation.formula} /> : null}
              <Formula expression={equation.result && equation.result.unit !== "-" ? `${equation.substituted}\\ \\text{${equation.result.unit}}` : equation.substituted} />
            </div>
          ))}
          {step.note ? <p className="chat-note">{shownSentence(step.note)}</p> : null}
          <p className="chat-note" data-testid="chat-working-source">From: {step.source}.</p>
        </li>
      ))}
    </ol>
  );
}
