import type { Metadata } from "next";
import Link from "next/link";
import { WORKSPACE_ROOT, workspace } from "@/lib/workspaces";
import "../../studio/studio.css";
import "../workspace.css";

export const metadata: Metadata = {
  title: "CAD | Anisotropy",
  description: "Geometry from a CAD file, planned: today a coupon's geometry is a few rows of the FEA workspace.",
};

/** The CAD workspace is a placeholder (ADR-0062): what it will do, and what exists today. Nothing here claims more than the repository backs. */
export default function CadWorkspacePage() {
  const cad = workspace("cad");
  return (
    <main id="main" className="studio-page ws-page">
      <div className="studio-heading">
        <span className="eyebrow">{cad.eyebrow} · PLANNED</span>
        <h1>Geometry from a CAD file.</h1>
        <p>Planned: {cad.detail}.</p>
      </div>
      <section className="studio-panel" data-testid="cad-placeholder">
        <h3>What exists today</h3>
        <p>Coupon geometry stated as a few dimensions and meshed from them: strips with tabs, a central hole, bending spans, and plates with named regions. Every deck we write shares that one geometry.</p>
        <h3>What is planned</h3>
        <p>Reading a STEP, IGES or STL file into the viewer, meshing it, and writing a CAD file for the shop and for other tools. The decision on how comes with its own record when the coupon work has been checked against tests.</p>
        <p><Link className="chat-link" href={`${WORKSPACE_ROOT}/fea`}>Open the coupon FEA workspace</Link> · <Link className="chat-link" href="/contact">Contact us</Link></p>
      </section>
    </main>
  );
}
