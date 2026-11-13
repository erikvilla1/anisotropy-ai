import { CouponVisual } from "@/components/coupon-visual";
import { ServicePage } from "@/components/services/service-page";
import { comingTests, listed, roadmap } from "@/lib/about-content";
import "../../inner-pages.css";
import "../services.css";

export const metadata = {
  title: "Finite element modeling",
  description: "A composite coupon test set up in the browser, checked against its standard, solved and shown ply by ply.",
};

const following = listed(comingTests);

/** The verification count quotes fea/checks/d3039-im7-8552/records/d3039-im7-8552-calculix.md (61 of 61 values within the
 * record's 3 % tolerance, the grip reaction within 0.78 %), in the workspace's own words for it (docs/copy-style-guide.md). */
export default function FiniteElementModeling() {
  return (
    <ServicePage
      slug="finite-element-modeling"
      headline={
        <>
          A coupon test,{" "}
          <br />
          <em>solved and shown ply by ply.</em>
        </>
      }
      lede="Give the material and the layup, or describe the coupon to the assistant. The workspace builds the unnotched tension coupon of ASTM D3039, checks the setup, solves it and shows the stresses, the displacement and the first ply to fail on a model you can turn."
      exists={[
        {
          title: "Unnotched tension first",
          text: `The unnotched tension coupon of ASTM D3039/D3039M, sized from Table 2 for its layup and checked clause by clause. ${following.charAt(0).toUpperCase() + following.slice(1)} follow, one test at a time.`,
        },
        {
          title: "A checklist before any run",
          text: "Units, geometry, test standard, material, laminate, supports, load, mesh, failure criterion and result points: each passes, warns or fails, and a failing setup never runs.",
        },
        {
          title: "Checked on every run",
          text: "Each run is also solved by an independent reference solver, and the comparison comes with the result.",
        },
        {
          title: "Every ply, both faces",
          text: "Stresses and strains in each ply, the failure index per criterion, the critical element and its ply, and the deformed shape at a scale you choose.",
        },
        {
          title: "The files you would otherwise make by hand",
          text: "The PDF report and the Abaqus input file (.inp), from one setup.",
        },
      ]}
      demonstration={{
        intro:
          "The IM7/8552 [45/0/-45/90]s tension coupon of ASTM D3039, verified against the reference solver: 61 of 61 values within 3 %, the grip reaction within 0.78 %.",
        media: (
          <div className="kit-figure">
            <div className="kit-figure-top">
              <span>COUPON / STRESS FIELD</span>
              <span className="kit-badge">ILLUSTRATIVE</span>
            </div>
            <CouponVisual mode="stress" />
            <p>An illustration of the field the workspace shows; the workspace draws the computed one.</p>
          </div>
        ),
        artefacts: [
          "The setup checklist, row by row",
          "The 3D view of the coupon with its supports and loads",
          "Per-ply stresses, strains and the failure index",
          "A plain-language explanation of the result",
          "Downloads: report (PDF), Abaqus input file (.inp)",
        ],
      }}
      // The same two stages, in the same words, as the roadmap on About (lib/about-content.ts).
      planned={roadmap.slice(2).map((stage) => ({ title: stage.title, text: stage.text }))}
      access={{
        text: "The workspace is open to invited users of the closed beta. Sign in with your invited email address and the one-time code we send you.",
        links: [
          { label: "Open the workspace", href: "/workspace/fea", primary: true },
          { label: "Not invited? Contact us", href: "/contact" },
        ],
      }}
    />
  );
}
