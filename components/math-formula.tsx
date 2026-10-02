import { useMemo } from "react";
import katex from "katex";
import { physicsLatex } from "@/lib/physics-latex";

export function MathFormula({ name }: { name: string }) {
  const expressions = physicsLatex[name];
  const markup = useMemo(() => expressions.map(expression => katex.renderToString(expression, {
    displayMode: true, output: "htmlAndMathml", throwOnError: true, strict: "error", trust: false,
  })), [expressions]);
  return <div className="physics-equation typeset-equation" role="group" aria-label={`${name} equation`} tabIndex={0}>
    {markup.map((html, i) => <div key={i} dangerouslySetInnerHTML={{ __html: html }} />)}
  </div>;
}
