"use client";

import { useId } from "react";

export function CouponVisual({
  mode = "stress",
  optimized = false,
}: {
  mode?: "geometry" | "stress" | "strain" | "failure";
  optimized?: boolean;
}) {
  const id = useId().replace(/:/g, "");
  const outline = optimized
    ? "M70 110 H160 Q205 110 242 140 H458 Q495 110 540 110 H630 V230 H540 Q495 230 458 200 H242 Q205 230 160 230 H70Z"
    : "M70 110 H175 Q218 110 235 145 H465 Q482 110 525 110 H630 V230 H525 Q482 230 465 195 H235 Q218 230 175 230 H70Z";
  return (
    <svg
      className="coupon-visual"
      viewBox="0 0 700 370"
      role="img"
      aria-label={`Conceptual ${optimized ? "revised" : "baseline"} coupon ${mode} illustration; no computed results`}
    >
      <defs>
        <linearGradient id={`${id}-field`}>
          <stop stopColor="#456b9b" />
          <stop offset=".23" stopColor="#63b5a0" />
          <stop
            offset=".36"
            stopColor={mode === "strain" ? "#bacb71" : "#e2a86b"}
          />
          <stop
            offset=".5"
            stopColor={mode === "strain" ? "#d9ac70" : "#b66b53"}
          />
          <stop offset=".64" stopColor="#e2a86b" />
          <stop offset=".77" stopColor="#63b5a0" />
          <stop offset="1" stopColor="#456b9b" />
        </linearGradient>
        <pattern
          id={`${id}-mesh`}
          width="13"
          height="10"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M13 0H0V10"
            fill="none"
            stroke="#0e181a"
            strokeWidth=".65"
            opacity=".7"
          />
        </pattern>
        <clipPath id={`${id}-clip`}>
          <path d={outline} />
        </clipPath>
      </defs>
      <g stroke="#344035" strokeWidth=".5" opacity=".5">
        {Array.from({ length: 12 }, (_, i) => (
          <path key={i} d={`M${i * 65} 40V320`} />
        ))}
        {Array.from({ length: 6 }, (_, i) => (
          <path key={i} d={`M25 ${i * 55 + 40}H675`} />
        ))}
      </g>
      <g transform="translate(0 3) rotate(-15 350 170)">
        <path
          d={outline}
          transform="translate(0 8)"
          fill="#344236"
          stroke="#63715e"
        />
        <path
          d={outline}
          fill={mode === "geometry" ? "#95b39f" : `url(#${id}-field)`}
          stroke="#b8ccab"
          strokeWidth="1.2"
        />
        <path d={outline} fill={`url(#${id}-mesh)`} />
        {mode === "failure" && (
          <g fill="none" stroke="#f2d0a3">
            <ellipse
              cx={optimized ? 280 : 231}
              cy="169"
              rx="31"
              ry="47"
              strokeWidth="2"
              strokeDasharray="5 4"
            />
            <path d={`M${optimized ? 280 : 231} 122V72H380`} />
            <text x="386" y="76" fill="#e7d6bd" stroke="none" fontSize="11">
              Region to investigate
            </text>
          </g>
        )}
        <g stroke="#b7c8ad" fill="none">
          <path d="M25 170H65M635 170H679M25 170l8 -5m-8 5 8 5M679 170l-8 -5m8 5 -8 5" />
        </g>
      </g>
      <text x="30" y="336" fill="#819078" fontSize="9" letterSpacing="1.5">
        {mode === "geometry"
          ? "PARAMETRIC GEOMETRY CONCEPT"
          : "QUALITATIVE FIELD ILLUSTRATION"}
      </text>
      <text x="670" y="336" textAnchor="end" fill="#819078" fontSize="9">
        ILLUSTRATION / NOT ANALYSIS
      </text>
    </svg>
  );
}
