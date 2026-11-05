import { MediaSlot } from "@/components/media-slot";
import { ServicePage } from "@/components/services/service-page";
import "../services.css";

export const metadata = {
  title: "Manufacturing plans — Anisotropy",
  description: "The ply book and the cure cycle from the same layup and material record. Planned, not built.",
};

export default function ManufacturingPlans() {
  return (
    <ServicePage
      slug="manufacturing-plans"
      headline={
        <>
          From the layup
          <br />
          <em>to the shop floor.</em>
        </>
      }
      lede="Not built yet. This page says what is intended, so that nothing on the site claims more than exists. The inputs it would start from are already part of every coupon."
      exists={[
        {
          title: "What it would start from",
          text: "The layup in laminate notation, the cited ply thickness and the material record exist for every coupon the studio solves.",
        },
        {
          title: "The fabrication side of the lab",
          text: "The team fabricates and tests its own coupons, so the plan would be written by the people who cut the plies.",
        },
      ]}
      demonstration={{
        intro: "There is nothing to show yet. The slot below is for a photograph of the lab's own layup once the service exists.",
        media: <MediaSlot label="Laying up a coupon panel in the lab" src="/assets/images/carbon-weave.jpg" alt="Woven carbon fiber" ratio="16/9" />,
        artefacts: ["A ply book and cut list", "A cure cycle from the material record", "A fabrication record linked to the test"],
        note: "Each item above is planned, not available.",
      }}
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
        text: "No access yet. If a manufacturing plan from a coupon record is what you need, write to us and say what the shop asks for.",
        links: [{ label: "Contact us", href: "/contact", primary: true }],
      }}
    />
  );
}
