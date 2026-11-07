"use client";

import { useEffect, useMemo, useState } from "react";
import { LaminateScene } from "./scene";
import { defaultHeroState } from "@/lib/home-calculator";
import { expandLayup } from "@/lib/layup";
import { angleSlots } from "@/lib/studio-colors";

const noHover = () => {};

/** The hero's lens (ADR-0066): the calculator's default stack, drawn by the same scene and turning slowly, for looking at
 * only. It shows no number; the calculator under the hero asks the engine for those (ADR-0001). */
export function HeroLens() {
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(media.matches);
    const onChange = () => setReducedMotion(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  const plies = useMemo(() => {
    const state = defaultHeroState();
    const angles = expandLayup(state.layup).layup?.angles ?? [];
    const colors = angleSlots(angles);
    const thickness = Number(state.thickness_mm) > 0 ? Number(state.thickness_mm) : 1;
    return angles.map((angle) => ({ angle_deg: angle, thickness_mm: thickness, color: colors.get(angle) ?? "#5d8f52" }));
  }, []);
  return <LaminateScene plies={plies} hovered={null} onHover={noHover} reducedMotion={reducedMotion} />;
}
