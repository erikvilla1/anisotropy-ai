"use client";

import dynamic from "next/dynamic";

/** The sketch loads only in the browser, as the scene does: three.js needs a WebGL context the static export's prerender has no use for. */
export const SketchScene = dynamic(() => import("./sketch-canvas").then((module) => module.SketchCanvas), {
  ssr: false,
  loading: () => <div className="studio-scene-loading" role="status">Loading the 3D view…</div>,
});
