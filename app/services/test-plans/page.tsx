import { MediaSlot } from "@/components/media-slot";
import { ServicePage } from "@/components/services/service-page";
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
      lede="A coupon's dimensions, tabs, hole, layup, material, load and failure criterion, in the proportions the standards ask for, checked line by line before a solver starts. The document a lab would file is not written yet."
      exists={[
        {
          title: "Coupons in standard proportions",
          text: "Tension after ASTM D3039, compression after D6641, open-hole tension after D5766, in-plane shear after D3518 and bending after D7264, as the proportions of the model, not as a certification.",
        },
        {
          title: "The checklist",
          text: "Twelve rows, from identity to the document, each one passing, warning or failing with the reason written next to it. A setup that fails does not run.",
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
          { label: "Describe a coupon", href: "/chat", primary: true },
          { label: "Contact us", href: "/contact" },
        ],
      }}
    />
  );
}
