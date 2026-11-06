import { CouponVisual } from "@/components/coupon-visual";
import { MediaSlot } from "@/components/media-slot";
import { ServicePage } from "@/components/services/service-page";
import "../services.css";

export const metadata = {
  title: "Computer-aided design — Anisotropy",
  description: "Coupon geometry stated as a few dimensions and meshed from them. A CAD file to take elsewhere is planned.",
};

export default function ComputerAidedDesign() {
  return (
    <ServicePage
      slug="computer-aided-design"
      headline={
        <>
          Geometry
          <br />
          <em>from a few numbers.</em>
        </>
      }
      lede="A coupon is its length, width, thickness, tabs and hole. The studio builds the mesh from those numbers, so the geometry and the model never disagree. A CAD file you can open elsewhere does not exist yet."
      exists={[
        {
          title: "Parametric coupons",
          text: "Strip coupons with or without a hole, with tabs and gauge probes placed from the dimensions; plates with named regions for supports and loads.",
        },
        {
          title: "Meshed from the spec",
          text: "Structured meshes for strips, a butterfly grid around the hole, and the element size as one row of the form.",
        },
        {
          title: "One geometry in every deck",
          text: "Abaqus, PrePoMax and our own kernel read the same spec, so the three models share every node.",
        },
      ]}
      demonstration={{
        intro: "The geometry is drawn as the mesh the solvers use, with the supports and the load marked on it.",
        media: (
          <>
            <MediaSlot label="The studio's mesh of an open-hole coupon" ratio="16/9" />
            <div className="concept-panel">
              <div className="concept-top">
                <span>COUPON / GEOMETRY</span>
                <span className="sample-badge">ILLUSTRATIVE</span>
              </div>
              <CouponVisual mode="geometry" />
              <p>An illustration of a strip coupon with a central hole.</p>
            </div>
          </>
        ),
        artefacts: [
          "The mesh, with its element size stated",
          "The supports and the loaded region, marked",
          "The decks that carry the geometry to other solvers",
        ],
      }}
      planned={[
        {
          title: "CAD export",
          text: "The coupon, and later a panel, as a STEP or IGES file for the shop and for other tools.",
        },
        {
          title: "Geometry beyond the coupon",
          text: "Stiffened panels and joints, once the coupon work has been checked against tests.",
        },
      ]}
      access={{
        text: "The geometry is part of every studio session, open to the invited users of the closed beta. For a CAD file today, write to us.",
        links: [
          { label: "Open the workspace", href: "/workspace/fea", primary: true },
          { label: "Contact us", href: "/contact" },
        ],
      }}
    />
  );
}
