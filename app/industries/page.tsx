import Link from "next/link";
import {
  ArrowRight,
  Plane,
  Wind,
  Ship,
  Car,
  Factory,
  GraduationCap,
} from "lucide-react";
import { ClosingBand } from "@/components/closing-band";
import "../inner-pages.css";
export const metadata = {
  title: "Industries",
  description: "Aerospace first, with research and education: composite coupons and materials analyzed from the evidence.",
};
const priorities = [
  {
    icon: Plane,
    title: "Aerospace",
    label: "PRIMARY INDUSTRY",
    text: "A research foundation for understanding lightweight composite structures. Start with the coupon and build toward more demanding structural questions.",
    use: [
      "Coupon and laminate characterization",
      "Material and layup trade studies",
      "Future wing optimization and repair analysis",
    ],
    href: "/contact",
    action: "Discuss an aerospace scope",
  },
  {
    icon: GraduationCap,
    title: "Research and education",
    label: "PRIORITY APPLICATION",
    text: "The materials library and detailed engineering explanations for the people investigating, teaching, and learning how laminates behave.",
    use: [
      "Source-linked material properties and thicknesses",
      "Classical laminate theory, ply stresses, and failure criteria, topic by topic",
      "Reproducible research and step-by-step methods",
    ],
    href: "/library",
    action: "Explore the materials library",
  },
];
const potential = [
  {
    icon: Wind,
    title: "Wind and energy",
    text: "Future laminate, blade, and repair studies grounded in relevant material and test evidence.",
  },
  {
    icon: Car,
    title: "Automotive and mobility",
    text: "Potential lightweight material screening and stiffness-to-mass trade studies.",
  },
  {
    icon: Ship,
    title: "Marine",
    text: "Potential applications in composite panels, environmental conditioning, and repair assessment.",
  },
  {
    icon: Factory,
    title: "Advanced manufacturing",
    text: "Future process-to-property studies linking fabrication conditions to measured behavior.",
  },
];
export default function Industries() {
  return (
    <main id="main" className="kit-page industries-page">
      <section className="page-opening">
        <p className="page-opening-label">INDUSTRIES / A FOCUSED START</p>
        <h1 className="page-opening-title">
          Built for research.{" "}
          <br />
          <em>Directed toward flight.</em>
        </h1>
        <div className="page-opening-grid">
          <div className="page-opening-copy">
            <p>
              Aerospace is our primary industry. Research and education are
              immediate priorities, with the materials library at the center
              of the experience.
            </p>
          </div>
          <div className="page-opening-note">
            <p className="page-opening-note-label">COUPONS FIRST</p>
            <p>
              Understand the material.
              <br />
              Validate the model.
              <br />
              Expand with the evidence.
            </p>
          </div>
        </div>
      </section>
      <section className="band is-light industry-priorities-band" aria-labelledby="industries-priorities">
        <div className="band-head is-label-only">
          <h2 className="band-label" id="industries-priorities">OUR PRIORITIES</h2>
        </div>
        <div className="industry-priorities">
          {priorities.map((s) => (
            <article className="industry-priority" key={s.title}>
              <div className="industry-priority-body">
                <div className="industry-priority-top">
                  <s.icon size={32} strokeWidth={1.2} aria-hidden="true" />
                  <span className="kit-mono">{s.label}</span>
                </div>
                <h3>{s.title}</h3>
                <p className="kit-text">{s.text}</p>
                <ul className="industry-uses">
                  {s.use.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
                <Link className="kit-link" href={s.href}>
                  {s.action}
                  {/* A no-break space inside a no-wrap span keeps the arrow with the last word when the link wraps. */}
                  <span className="kit-link-icon">
                    {"\u00a0"}
                    <ArrowRight size={16} aria-hidden="true" />
                  </span>
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="band industry-potentials-band" aria-labelledby="industries-potential">
        <div className="band-head">
          <p className="band-label">BEYOND THE INITIAL FOCUS</p>
          <div className="band-statement">
            <h2 id="industries-potential">Potential industries.</h2>
            <p>
              The same need to understand composites appears in other sectors.
              These are future opportunities, each requiring its own applicable
              physics and validation.
            </p>
          </div>
        </div>
        <div className="industry-potentials">
          {potential.map((s) => (
            <article className="industry-potential" key={s.title}>
              <div className="industry-potential-body">
                <s.icon size={26} strokeWidth={1.3} aria-hidden="true" />
                <h3 className="kit-title">{s.title}</h3>
                <p>{s.text}</p>
              </div>
            </article>
          ))}
        </div>
        <div className="kit-note">
          <p className="kit-note-text">
            Anisotropy works at coupon scale today. Structural applications
            are our direction, not component-level validation or
            certification.
          </p>
        </div>
      </section>
      <ClosingBand
        label="BEGIN WITH THE ENGINEERING QUESTION"
        heading={["What does your", "material need to do?"]}
        action={{ label: "Tell us what it needs to do", href: "/contact" }}
      />
    </main>
  );
}
