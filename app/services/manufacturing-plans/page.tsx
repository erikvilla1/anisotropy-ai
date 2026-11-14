import { ServicePage } from "@/components/services/service-page";
import "../../inner-pages.css";
import "../services.css";

export const metadata = {
  title: "Manufacturing plans",
  description: "Planned: a ply book and cure cycle from the same layup and material record.",
};

/** A planned service (ADR-0058; kept as a short page, the audit of 2026-11-12, decision D17): what it would start from, what is
 * planned, and a way to ask about it. There is nothing to demonstrate yet, so the page has no demonstration. */
export default function ManufacturingPlans() {
  return (
    <ServicePage
      slug="manufacturing-plans"
      headline={
        <>
          From the layup{" "}
          <br />
          <em>to the shop floor.</em>
        </>
      }
      lede="A ply book, a cut list and a cure cycle, written from the same layup and material record the analysis used."
      exists={[
        {
          title: "What it would start from",
          text: "The layup in laminate notation, the cited ply thickness and the material record exist for every coupon the workspace solves.",
        },
        {
          title: "Written by people who build coupons",
          text: "We fabricate and test our own coupons, so the plan comes from the same hands that cut the plies.",
        },
      ]}
      planned={[
        {
          title: "Ply book and cut list",
          text: "Each ply with its angle, size and order, from the same layup the model used.",
        },
        {
          title: "Cure cycle from the record",
          text: "The cycle the material's source prescribes, carried with the material record rather than copied by hand.",
        },
        {
          title: "Fabrication record",
          text: "What was laid up, by whom and when, linked to the coupon's test and to its model.",
        },
      ]}
      access={{
        text: "Need a manufacturing plan from a coupon record? Tell us what your shop asks for.",
        links: [{ label: "Contact us", href: "/contact", primary: true }],
      }}
    />
  );
}
