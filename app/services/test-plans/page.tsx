import { MediaSlot } from "@/components/media-slot";
import { ServicePage } from "@/components/services/service-page";
import "../../inner-pages.css";
import "../services.css";

export const metadata = {
  title: "Test plans — Anisotropy",
  description: "Coupons in the proportions of the ASTM standards, with a checklist that judges the setup before anything runs. The test-plan document is planned.",
};

export default function TestPlans() {
  return (
    <ServicePage
      slug="test-plans"
      headline={
        <>
          The test,
          <br />
          <em>stated before it runs.</em>
        </>
      }
      lede="A coupon's dimensions, tabs, hole, layup, material, load and failure criterion, checked line by line before a solver starts, and against the clauses of the test standard you pick. The document a lab would file is not written yet."
      exists={[
        {
          title: "The standard, clause by clause",
          text: "Pick ASTM D3039/D3039M for tension or ASTM C1869 for open-hole tension of ceramic composites, and every requirement the model can meet is judged with its clause: the coupon's value beside what the clause asks, a deviation reported and never hidden, the procedure left to the laboratory. Not a certification. A carbon fibre tow's record under ASTM D4018 is reduced to each specimen's strength and chord modulus and their statistics with no model, and judged against its clauses the same way. Compression, polymer open-hole, shear and bending keep the proportions of D6641, D5766, D3518 and D7264 until those standards are added.",
        },
        {
          title: "The checklist",
          text: "Thirteen rows, from identity to the document, the test standard among them, each one passing, warning or failing with the reason written next to it. A setup that fails does not run.",
        },
        {
          title: "The input form",
          text: "A spreadsheet form the team fills, with a Definitions sheet that explains every row. The chat and the studio fill the same rows.",
        },
      ]}
      demonstration={{
        intro: "The chat asks one thing at a time; the form shows every row at once. Both end in the same checked setup.",
        media: <MediaSlot label="Coupon specimens before a tensile test" src="/assets/images/coupon-01.jpg" alt="A composite coupon specimen" ratio="16/9" />,
        artefacts: [
          "The coupon's values as one file",
          "The checklist with its verdicts",
          "The model preview with supports and loads marked",
        ],
      }}
      planned={[
        {
          title: "The test-plan document",
          text: "Specimen count, conditioning, instrumentation, the loading sequence and the acceptance criteria, written out from the same record for the lab.",
        },
        {
          title: "Sign-off",
          text: "A plan is approved before a coupon is cut. The platform would hold the approved version next to the result.",
        },
      ]}
      access={{
        text: "Describe a coupon in the chat and the checklist judges it at once. The document itself is planned; write to us if you need one now.",
        links: [
          { label: "Describe a coupon", href: "/workspace/fea", primary: true },
          { label: "Contact us", href: "/contact" },
        ],
      }}
    />
  );
}
