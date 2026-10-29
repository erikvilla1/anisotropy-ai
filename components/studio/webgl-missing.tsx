"use client";

export function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export function WebGLMissing() {
  return (
    <div className="studio-webgl-missing" role="status" data-testid="webgl-missing">
      <strong>This browser gives no WebGL context, so the 3D view cannot draw.</strong>
      <p>The numbers, the checklist, the summary and the explanation below are complete without it. Try another browser, or enable hardware acceleration.</p>
    </div>
  );
}
