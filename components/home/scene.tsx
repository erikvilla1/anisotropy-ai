"use client";

import dynamic from "next/dynamic";

/** The laminate view loads only in the browser: three.js needs a WebGL context, which the static export's prerender has no use for
 * (the pattern of components/studio/scene.tsx). */
export const LaminateScene = dynamic(() => import("./laminate-scene").then((module) => module.LaminateSceneCanvas), {
  ssr: false,
  loading: () => <div className="studio-scene-loading hero-laminate-loading" role="status">Loading the 3D view…</div>,
});
