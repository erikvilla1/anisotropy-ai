"use client";

import { useMemo, useState } from "react";
import { LaminateScene } from "@/components/home/scene";
import { useLaminate } from "@/components/studio/laminate-context";
import { LaminateResults } from "@/components/studio/laminate-results";
import { plyLabel, problemLines } from "@/lib/laminate-chat";
import { formatNumber } from "@/lib/number-format";
import { angleSlots } from "@/lib/studio-colors";

/** The centre of the laminate workspace (ADR-0062, part 5): the problem as stated, the stack drawn ply by ply as soon as the layup is
 * given (angles only, nothing computed, ADR-0001), and the engine's answer below it in the units picked there (ADR-0060). The drawing
 * is an image with its plies in words, and each ply can be picked by keyboard or touch as well as by pointing (WCAG 1.1.1, 2.1.1). */
export function LaminateStage() {
  const { draft, answer, solving, solve } = useLaminate();
  const lines = problemLines(draft);
  const angles = draft.layup?.angles ?? [];
  const [hovered, setHovered] = useState<number | null>(null);
  const plies = useMemo(() => {
    const colors = angleSlots(angles);
    return angles.map((angle) => ({ angle_deg: angle, thickness_mm: 1, color: colors.get(angle) ?? "#5d8f52" }));
  }, [angles.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const degrees = (angle: number) => `${formatNumber(angle, { zeros: false })}°`;
  return (
    <section className="studio-output">
      <dl className="chat-spec lam-spec" data-testid="laminate-spec">
        {lines.map(([k, v]) => <div key={k} data-filled={v ? "yes" : "no"}><dt>{k}</dt><dd>{v || "–"}</dd></div>)}
      </dl>
      {angles.length ? (
        <div className="studio-panel" data-testid="laminate-stack">
          <h3>The stack <span className="studio-badge">{angles.length} plies, bottom ply first</span></h3>
          <div className="ws-stage-stack" role="img" aria-label={`${angles.length} plies, bottom to top: ${angles.map(degrees).join(", ")}`}>
            <LaminateScene plies={plies} hovered={hovered} onHover={setHovered} reducedMotion={true} decor={false} />
          </div>
          <div className="lam-ply-chips" role="group" aria-label="Plies, bottom first">
            {angles.map((angle, index) => (
              <button type="button" key={index} data-active={hovered === index ? "" : undefined} onFocus={() => setHovered(index)} onBlur={() => setHovered(null)}
                onMouseEnter={() => setHovered(index)} onMouseLeave={() => setHovered(null)} onClick={() => setHovered(index)}>
                {plyLabel(index + 1, angle)}</button>
            ))}
          </div>
          {/* not a live region: a chip says its own ply when it takes focus, and pointing at the drawing is not announced */}
          <p className="studio-muted">{hovered !== null && angles[hovered] !== undefined ? `${plyLabel(hovered + 1, angles[hovered])}. ` : "Point to a ply, or pick it below, to see its angle. "}
            The grain follows the fibres; the drawn thickness is a shape, not a scale.</p>
        </div>
      ) : (
        <div className="studio-empty" data-testid="empty-stack">
          <h3>No stack yet</h3>
          <p>The stack is drawn here once you enter a layup.</p>
        </div>
      )}
      {answer ? <LaminateResults answer={answer} busy={solving} onReport={(system) => void solve(system)} /> : (
        <div className="studio-empty" data-testid="empty-answer">
          <h3>No results yet</h3>
          <p>Results appear here after you solve: A, B and D, strains, ply stresses and first-ply failure.</p>
        </div>
      )}
    </section>
  );
}
