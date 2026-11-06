"use client";

import { useMemo, useState } from "react";
import { LaminateScene } from "@/components/home/scene";
import { useLaminate } from "@/components/studio/laminate-context";
import { LaminateResults } from "@/components/studio/laminate-results";
import { problemLines } from "@/lib/laminate-chat";
import { angleSlots } from "@/lib/studio-colors";

/** The centre of the laminate workspace (ADR-0062, part 5): the problem as stated, the stack drawn ply by ply as soon as the layup is
 * given (angles only, nothing computed, ADR-0001), and the engine's answer below it in the units picked there (ADR-0060). */
export function LaminateStage() {
  const { draft, answer, solving, solve } = useLaminate();
  const lines = problemLines(draft);
  const angles = draft.layup?.angles ?? [];
  const [hovered, setHovered] = useState<number | null>(null);
  const plies = useMemo(() => {
    const colors = angleSlots(angles);
    return angles.map((angle) => ({ angle_deg: angle, thickness_mm: 1, color: colors.get(angle) ?? "#5d8f52" }));
  }, [angles.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <section className="studio-output">
      <dl className="chat-spec lam-spec" data-testid="laminate-spec">
        {lines.map(([k, v]) => <div key={k} data-filled={v ? "yes" : "no"}><dt>{k}</dt><dd>{v || "–"}</dd></div>)}
      </dl>
      {angles.length ? (
        <div className="studio-panel" data-testid="laminate-stack">
          <h3>The stack <span className="studio-badge">{angles.length} plies, bottom face first</span></h3>
          <div className="ws-stage-stack">
            <LaminateScene plies={plies} hovered={hovered} onHover={setHovered} reducedMotion={true} decor={false} />
          </div>
          <p className="studio-muted">{hovered !== null && angles[hovered] !== undefined ? `Ply ${hovered + 1}: ${angles[hovered]}°. ` : "Hover a ply for its angle. "}
            Stripes follow the fibres; the drawn thickness is a shape, not a scale.</p>
        </div>
      ) : (
        <div className="studio-empty" data-testid="empty-stack">
          <h3>No stack yet</h3>
          <p>Give the layup under Layup, or tell the assistant, and it is drawn here ply by ply.</p>
        </div>
      )}
      {answer ? <LaminateResults answer={answer} busy={solving} onReport={(system) => void solve(system)} /> : (
        <div className="studio-empty" data-testid="empty-answer">
          <h3>The answer appears here</h3>
          <p>Once the problem is stated, the engine solves it in seconds: the A, B, D matrices, the strains, every ply&apos;s stresses and first-ply failure, in the units you pick.</p>
        </div>
      )}
    </section>
  );
}
