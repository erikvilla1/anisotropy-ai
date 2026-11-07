"use client";

import { useMemo, useState } from "react";
import { FieldGrid, PlyGrid } from "@/components/studio/coupon-form";
import { LaminateScene } from "@/components/home/scene";
import { angleSlots } from "@/lib/studio-colors";
import { layupNotation, layupRows, parseLayup, pliesOf } from "@/lib/studio-chat";
import type { StudioForm } from "@/lib/studio-form";

const NUMBER = /^[+-]?(?:\d+\.?\d*|\.\d+)$/;

/** The layup as the engineer states it: the notation (read by the chat's reader, so `[45/0/-45/90]s` typed here and in the chat are the
 * same rows), the ply rows themselves, whether the stack is symmetric, the ply thickness, and the stack drawn ply by ply, bottom face
 * first (ADR-0004). The drawing shows angles only; no laminate quantity is computed (ADR-0001). */
export function LayupEditor({ form, errors, disabled, onChange, onRows }: {
  form: StudioForm; errors: Record<string, string>; disabled: boolean; onChange: (key: string, value: string) => void; onRows: (rows: StudioForm) => void;
}) {
  const [text, setText] = useState(() => layupNotation(form));
  const [error, setError] = useState("");
  const [hovered, setHovered] = useState<number | null>(null);
  const listed = pliesOf(form).filter((value) => NUMBER.test(value)).map(Number);
  const angles = useMemo(() => (form.symmetric === "yes" ? [...listed, ...[...listed].reverse()] : listed), [listed.join(","), form.symmetric]); // eslint-disable-line react-hooks/exhaustive-deps
  const colors = useMemo(() => angleSlots(angles), [angles]);
  const plies = useMemo(() => angles.map((angle) => ({ angle_deg: angle, thickness_mm: 1, color: colors.get(angle) ?? "#5d8f52" })), [angles, colors]);
  return (
    <div className="ws-layup" data-testid="layup-editor">
      <form className="chat-inline ws-layup-notation" onSubmit={(e) => {
        e.preventDefault();
        const layup = parseLayup(text);
        if (!layup) { setError("Write it as [45/0/-45/90]s, [0/90]2s or [±45]2s, up to 16 plies listed."); return; }
        setError("");
        onRows(layupRows(layup));
      }}>
        <input type="text" aria-label="Layup notation" placeholder="[45/0/-45/90]s" value={text} disabled={disabled} autoComplete="off"
          onChange={(e) => { setText(e.target.value); setError(""); }} />
        <button type="submit" className="chat-primary" disabled={disabled}>Use layup</button>
        {error ? <span className="chat-error" role="alert">{error}</span> : null}
      </form>
      <PlyGrid form={form} errors={errors} disabled={disabled} onChange={onChange} />
      <FieldGrid form={form} keys={["symmetric", "ply_thickness"]} errors={errors} disabled={disabled} onChange={onChange} />
      {angles.length ? (
        <div className="ws-layup-stack">
          <LaminateScene plies={plies} hovered={hovered} onHover={setHovered} reducedMotion={true} decor={false} />
          <p className="studio-hint">{angles.length} plies drawn bottom face first, {form.symmetric === "yes" ? "mirrored at the midplane" : "as listed"}; hover a ply for its angle. Stripes follow the fibres; the drawn thickness is a shape, not a scale.</p>
        </div>
      ) : null}
    </div>
  );
}
