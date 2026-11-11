import { CouponVisual } from "@/components/coupon-visual";
import { MediaSlot } from "@/components/media-slot";
import { ServicePage } from "@/components/services/service-page";
import "../../inner-pages.css";
import "../services.css";

export const metadata = {
  title: "Finite element modeling — Anisotropy",
  description: "A composite coupon test set up in the browser, checked, solved with our finite element kernel and CalculiX, and shown ply by ply.",
};

export default function FiniteElementModeling() {
  return (
    <ServicePage
      slug="finite-element-modeling"
      headline={
        <>
          A coupon test,
          <br />
          <em>solved and shown ply by ply.</em>
        </>
      }
      lede="Describe the test in words or fill the form. The studio checks the setup, solves it with our finite element kernel and with CalculiX, and shows the stresses, the displacement and the first ply to fail on a model you can turn."
      exists={[
        {
          title: "Six test kinds and a plate",
          text: "Unnotched tension and compression, open-hole tension, in-plane shear, three- and four-point bending, in the proportions of ASTM D3039, D6641, D5766, D3518 and D7264, the tension coupon checked clause by clause against ASTM D3039/D3039M when you pick it, the open hole against ASTM C1869 for ceramic composites; and a plate held and loaded on regions you name.",
        },
        {
          title: "A checklist before any run",
          text: "Identity, units, geometry, material, laminate, constraints, load, mesh, criterion, probes and solver: each row passes, warns or fails, and a failing setup never runs.",
        },
        {
          title: "Two solvers, one record",
          text: "Our membrane and shell kernels work on the laminate's own stiffness; CalculiX solves the same deck as the reference, and the comparison is part of the result.",
        },
        {
          title: "Every ply, both faces",
          text: "Stresses and strains in each ply, the failure index per criterion, the critical element and its ply, and the deformed shape at a scale you choose.",
        },
        {
          title: "The files you would otherwise make by hand",
          text: "Abaqus and PrePoMax decks, the fields for a viewer, the PDF package and the run record, all from one spec.",
        },
      ]}
      demonstration={{
        intro:
          "Our first bending coupon, IM7/8552 in ASTM D7264 proportions, against CalculiX S8R: 100 numbers within 3 %, the nose reaction within 0.12 %. The decks and the record are in the repository.",
        media: (
          <>
            <MediaSlot label="A solved open-hole coupon in the studio: the critical ply and its failure index" ratio="16/9" />
            <div className="kit-figure">
              <div className="kit-figure-top">
                <span>COUPON / STRESS FIELD</span>
                <span className="kit-badge">ILLUSTRATIVE</span>
              </div>
              <CouponVisual mode="stress" />
              <p>An illustration of the field the studio shows; the studio draws the computed one.</p>
            </div>
          </>
        ),
        artefacts: [
          "The setup checklist, row by row",
          "The 3D view of the coupon with its supports and loads",
          "Per-ply stresses, strains and the failure index",
          "The explanation of the result, from the engine's fact sheet",
          "The downloads: package, PDF, decks, fields",
        ],
      }}
      planned={[
        {
          title: "Elements and joints",
          text: "Progressive damage, joints and repair analysis, developed through element tests after the coupon work holds up.",
        },
        {
          title: "Panels and structures",
          text: "Stiffened panels and buckling, carried forward only from a verified coupon foundation.",
        },
      ]}
      access={{
        text: "The chat runs at anisotropy.dev for the invited users of the closed beta. Sign in with the email on the invite list; a one-time code arrives by mail. Accounts for everyone else are not open yet.",
        links: [
          { label: "Open the workspace", href: "/workspace/fea", primary: true },
          { label: "Not invited? Contact us", href: "/contact" },
        ],
      }}
    />
  );
}
