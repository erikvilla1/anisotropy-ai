import Link from "next/link";
import { ServicePage } from "@/components/services/service-page";
import "../../inner-pages.css";
import "../services.css";

export const metadata = {
  title: "Documentation",
  description: "Every solved coupon leaves a report, every calculation a record, and every material value carries the page it came from.",
};

export default function Documentation() {
  return (
    <ServicePage
      slug="documentation"
      headline={
        <>
          Every answer with{" "}
          <br />
          <em>its assumptions and references.</em>
        </>
      }
      lede="A result nobody can trace is not finished. Each solved coupon leaves a report, each calculation leaves a record, and each material value carries the page it came from, so any answer can be checked."
      exists={[
        {
          title: "The coupon report",
          text: "One report per solved coupon: the model, the theory it used and the reference solver check, with the Abaqus input file (.inp) beside it.",
        },
        {
          title: "A record of every run",
          text: "The inputs as entered, the software version and the result, kept so any number traces back to the run that produced it.",
        },
        {
          title: "Materials with their page",
          text: "The library states each property's source, page and printed unit, and the calculator shows the citation of every value it used.",
        },
        {
          title: "The physics, with references",
          text: "Each equation the analysis uses has a card in the library with its reference, so the method is as open as the number.",
        },
      ]}
      demonstration={{
        intro: "The report reads like one an engineer would write by hand, except that every number in it comes from the run it documents.",
        artefacts: ["Report (PDF)", "Abaqus input file (.inp)"],
      }}
      planned={[
        {
          title: "Test-plan and manufacturing documents",
          text: (
            <>
              The same record, written out as the document the lab or the shop needs. See{" "}
              <Link href="/services/test-plans">Test plans</Link> and{" "}
              <Link href="/services/manufacturing-plans">Manufacturing plans</Link>.
            </>
          ),
        },
      ]}
      access={{
        text: "Every analysis comes with its report. The materials library and the physics cards are open to every user.",
        links: [
          { label: "Open the workspace", href: "/workspace/fea", primary: true },
          { label: "Browse the materials library", href: "/library" },
        ],
      }}
    />
  );
}
