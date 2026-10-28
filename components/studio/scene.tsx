"use client";

import dynamic from "next/dynamic";

/** The 3D view loads only in the browser: three.js needs a WebGL context, which the static export's prerender has no use for. */
export const Scene = dynamic(() => import("./scene-canvas").then((module) => module.SceneCanvas), {
  ssr: false,
  loading: () => <div className="studio-scene-loading" role="status">Loading the 3D view…</div>,
});
