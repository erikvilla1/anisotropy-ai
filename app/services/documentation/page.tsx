import { MediaSlot } from "@/components/media-slot";
import { ServicePage } from "@/components/services/service-page";
import "../../inner-pages.css";
import "../services.css";

export const metadata = {
  title: "Documentation",
  description: "Every solved coupon leaves a package, every calculation a record, and every material value carries the page it came from.",
};

export default function Documentation() {
  return (
    <ServicePage
      slug="documentation"
      headline={
        <>
          Every answer with
          <br />
          <em>its assumptions and references.</em>
        </>
      }
      lede="A result nobody can trace is not finished. Each coupon job leaves a package, each calculation leaves a record, and each material value carries the page it came from, so an engineer can verify the answer and a student can learn from it."
      exists={[
        {
          title: "The coupon package",
          text: "One folder per solved coupon: a PDF with the model, the theory it used, the comparison with CalculiX and the audit form, next to the decks, the fields and the record.",
        },
        {
          title: "A record of every run",
          text: "The inputs as received, the engine and API versions, the commit and the result, kept so any number can be traced back to the run that produced it.",
        },
        {
          title: "Materials with their page",
          text: "The library states each property's source, page and printed unit, and the calculator shows the citation of every value it used.",
        },
        {
          title: "The physics, with references",
          text: "Each equation the engine implements has a card in the library with its reference, so the method is as inspectable as the number.",
        },
      ]}
      demonstration={{
        intro: "A package reads like a report an engineer would write by hand, except that every number in it comes from the run it documents.",
        media: <MediaSlot label="Pages of a coupon package: the model chapter and the comparison table" ratio="16/9" />,
        artefacts: [
          "The report as PDF, with its LaTeX source",
          "Abaqus and PrePoMax decks as written",
          "The comparison record against the reference solver",
          "The run record with inputs, versions and result",
        ],
      }}
      planned={[
        {
          title: "Test-plan and manufacturing documents",
          text: "The same record, written out as the document the lab or the shop needs. See the test plans and manufacturing plans pages.",
        },
      ]}
      access={{
        text: "The package comes with every studio job, so it is available to the invited users of the closed beta. The materials library and the physics cards are open to anyone who can reach the site.",
        links: [
          { label: "Open the workspace", href: "/workspace/fea", primary: true },
          { label: "Browse the materials library", href: "/library" },
        ],
      }}
    />
  );
}
