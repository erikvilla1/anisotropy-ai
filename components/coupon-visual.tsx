"use client";

import { useId } from "react";

/** The strip, from end to end along the drawing's x, and the bonded tabs at its ends. */
const STRIP = { x0: 70, x1: 630, y0: 150, y1: 190 };
const TAB = 100;
const outline = `M${STRIP.x0} ${STRIP.y0} H${STRIP.x1} V${STRIP.y1} H${STRIP.x0}Z`;
const tab = (x: number, inward: 1 | -1) => {
  const end = x + inward * TAB;
  // A tapered tab: its end towards the gauge is bevelled, as D3039's tabs are.
  return `M${x} ${STRIP.y0 - 5} H${end - inward * 14} L${end} ${STRIP.y0} V${STRIP.y1} L${end - inward * 14} ${STRIP.y1 + 5} H${x}Z`;
};
/** Where the tab ends fall along the strip, as a fraction of its length: the gauge section lies between them. */
const TAB_END = TAB / (STRIP.x1 - STRIP.x0);

/** An illustration, not a result: the ASTM D3039 tension strip, straight-sided with bonded tabs (the one coupon the workspace
 * offers), drawn for a dark ground. `stress` colours the gauge section one colour, raised only at the tab ends, as a uniform
 * tension strip is; `failure` marks the tab end as the region to investigate. Its words are the page's: the figure's bar and
 * caption carry them (audit of 2026-11-12, services-8 and about-industries-contact-24). */
export function CouponVisual({ mode = "stress" }: { mode?: "geometry" | "stress" | "strain" | "failure" }) {
  const id = useId().replace(/:/g, "");
  const gauge = mode === "strain" ? "#d9ac70" : "#e2a86b";
  const peak = mode === "strain" ? "#bacb71" : "#b66b53";
  const names: Record<typeof mode, string> = {
    geometry: "geometry",
    stress: "stress field",
    strain: "strain field",
    failure: "region to investigate at a tab end",
  };
  return (
    <svg
      className="coupon-visual"
      viewBox="0 0 700 370"
      role="img"
      aria-label={`Illustration of the ASTM D3039 tension strip with bonded tabs, its ${names[mode]}; no computed results`}
    >
      <defs>
        <linearGradient id={`${id}-field`}>
          <stop stopColor="#456b9b" />
          <stop offset={TAB_END - 0.06} stopColor="#63b5a0" />
          <stop offset={TAB_END} stopColor={peak} />
          <stop offset={TAB_END + 0.03} stopColor={gauge} />
          <stop offset={1 - TAB_END - 0.03} stopColor={gauge} />
          <stop offset={1 - TAB_END} stopColor={peak} />
          <stop offset={1 - TAB_END + 0.06} stopColor="#63b5a0" />
          <stop offset="1" stopColor="#456b9b" />
        </linearGradient>
        <pattern id={`${id}-mesh`} width="14" height="10" patternUnits="userSpaceOnUse">
          <path d="M14 0H0V10" fill="none" stroke="#0e181a" strokeWidth=".65" opacity=".7" />
        </pattern>
      </defs>
      <g stroke="#3c3c3c" strokeWidth=".5" opacity=".5">
        {Array.from({ length: 12 }, (_, i) => (
          <path key={i} d={`M${i * 65} 40V320`} />
        ))}
        {Array.from({ length: 6 }, (_, i) => (
          <path key={i} d={`M25 ${i * 55 + 40}H675`} />
        ))}
      </g>
      <g transform="translate(0 3) rotate(-15 350 170)">
        <path d={outline} transform="translate(0 8)" fill="#3e3e3e" stroke="#6c6c6c" />
        <path d={outline} fill={mode === "geometry" ? "#aaaaaa" : `url(#${id}-field)`} stroke="#c4c4c4" strokeWidth="1.2" />
        <path d={outline} fill={`url(#${id}-mesh)`} />
        {[tab(STRIP.x0, 1), tab(STRIP.x1, -1)].map((d) => (
          <g key={d}>
            <path d={d} transform="translate(0 6)" fill="#2c2c2c" stroke="#5a5a5a" />
            <path d={d} fill="#7b7b7b" stroke="#c4c4c4" strokeWidth="1.2" />
          </g>
        ))}
        {mode === "failure" && (
          <ellipse
            cx={STRIP.x0 + TAB}
            cy={(STRIP.y0 + STRIP.y1) / 2}
            rx="24"
            ry="40"
            fill="none"
            stroke="#f2d0a3"
            strokeWidth="2"
            strokeDasharray="5 4"
          />
        )}
        <g stroke="#c1c1c1" fill="none">
          <path d="M25 170H65M635 170H679M25 170l8 -5m-8 5 8 5M679 170l-8 -5m8 5 -8 5" />
        </g>
      </g>
    </svg>
  );
}
