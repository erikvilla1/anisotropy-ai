import { MediaSlot } from "@/components/media-slot";
import { ServicePage } from "@/components/services/service-page";
import "../../inner-pages.css";
import "../services.css";

export const metadata = {
  title: "Test plans",
  description: "Coupons sized to ASTM D3039, with a setup check against its clauses before anything runs. The test-plan document is planned.",
};

export default function TestPlans() {
  return (
    <ServicePage
      slug="test-plans"
      headline={
        <>
          The test,{" "}
          <br />
          <em>stated before it runs.</em>
        </>
      }
      lede="A coupon's dimensions, tabs, layup, material, load and failure criterion, checked line by line before the solver starts, and against the clauses of ASTM D3039 when you choose it. The test-plan document is planned."
      exists={[
        {
          title: "The standard, clause by clause",
          text: "ASTM D3039/D3039M, tension. Every requirement the model can meet is checked against its clause: the coupon's value beside the clause's limit, with any deviation reported. Laboratory procedure stays with the lab. A setup check, not a certification. More standards follow, one test at a time.",
        },
        {
          title: "The checklist",
          text: "Every setup item, the test standard among them, passes, warns or fails with the reason beside it. A setup that fails does not run.",
        },
        {
          title: "Two ways in",
          text: "Describe the coupon to the assistant, or fill the setup panels; both end in the same checked setup.",
        },
      ]}
      demonstration={{
        intro: "The assistant asks one thing at a time; the setup panels show every value at once.",
        media: <MediaSlot label="Coupon specimens before a tensile test" src="/assets/images/coupon-01.jpg" alt="A composite coupon specimen" ratio="16/9" />,
        artefacts: [
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
        text: "Describe a coupon to the assistant and the checklist judges it at once. The document itself is planned; write to us if you need one now.",
        links: [
          { label: "Describe a coupon", href: "/workspace/fea", primary: true },
          { label: "Contact us", href: "/contact" },
        ],
      }}
    />
  );
}
