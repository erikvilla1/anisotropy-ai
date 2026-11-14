import { CouponVisual } from "@/components/coupon-visual";
import { ServicePage } from "@/components/services/service-page";
import "../../inner-pages.css";
import "../services.css";

export const metadata = {
  title: "Computer-aided design",
  description: "Coupon geometry stated as a few dimensions and meshed from them. A CAD file to take elsewhere is planned.",
};

export default function ComputerAidedDesign() {
  return (
    <ServicePage
      slug="computer-aided-design"
      headline={
        <>
          Geometry{" "}
          <br />
          <em>from a few numbers.</em>
        </>
      }
      lede="A coupon is its length, width, thickness and tabs. The workspace builds the mesh from those numbers, so the geometry and the model never disagree. A CAD file you can open elsewhere does not exist yet."
      exists={[
        {
          title: "Parametric coupons",
          text: "The D3039 tension strip, with its tabs and extensometer placed from the dimensions D3039 Table 2 gives for the layup. Holes, bending spans and plates follow, one test at a time.",
        },
        {
          title: "Meshed from the dimensions",
          text: "A structured mesh for the strip, with the element size as one setting.",
        },
        {
          title: "One geometry, every file",
          text: "The mesh you see and the Abaqus input file (.inp) come from the same dimensions, node for node.",
        },
      ]}
      demonstration={{
        intro: "The geometry is drawn as the mesh the analysis uses, with the supports and the load marked on it.",
        media: (
          <div className="kit-figure">
            <div className="kit-figure-top">
              <span>COUPON / GEOMETRY</span>
              <span className="kit-badge">ILLUSTRATIVE</span>
            </div>
            <CouponVisual mode="geometry" />
            <p>An illustration of the D3039 tension strip with its tabs.</p>
          </div>
        ),
        artefacts: [
          "The mesh, with its element size stated",
          "The supports and the loaded region, marked",
          "The Abaqus input file (.inp) that carries the geometry to other programs",
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
        text: "The geometry is part of every workspace session for invited beta users. CAD export is planned; write to us if you need it.",
        links: [
          { label: "Open the workspace", href: "/workspace/fea", primary: true },
          { label: "Contact us", href: "/contact" },
        ],
      }}
    />
  );
}
