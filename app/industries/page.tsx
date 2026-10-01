import Link from "next/link";
import {
  ArrowUpRight,
  Plane,
  Wind,
  Ship,
  Car,
  Factory,
  GraduationCap,
} from "lucide-react";
export const metadata = { title: "Industries — Anisotropy AI" };
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
    href: "/chat",
    action: "Define an aerospace research scope",
  },
  {
    icon: GraduationCap,
    title: "Research & education",
    label: "PRIORITY APPLICATION",
    text: "A composites material library and detailed engineering explanations for the people investigating, teaching, and learning how laminates behave.",
    use: [
      "Source-linked properties, layups, and thicknesses",
      "CLT, local stresses, and failure criteria by topic",
      "Reproducible research and step-by-step methods",
    ],
    href: "/library",
    action: "Explore the materials & physics library",
  },
];
const potential = [
  {
    icon: Wind,
    title: "Wind & energy",
    text: "Future laminate, blade, and repair studies grounded in relevant material and test evidence.",
  },
  {
    icon: Car,
    title: "Automotive & mobility",
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
    <main id="main" className="inner-page">
      <section className="section page-intro">
        <span className="eyebrow">INDUSTRIES / A FOCUSED START</span>
        <div className="intro-grid">
          <div>
            <h1>
              Built for research.
              <br />
              <em>Directed toward flight.</em>
            </h1>
            <p>
              Aerospace is our primary industry. Research and education are
              immediate priorities, with a composites material library at the
              center of the experience.
            </p>
          </div>
          <div className="intro-aside">
            <span className="status-dot" />
            <span>COUPONS FIRST</span>
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
      <section className="section industry-section">
        <span className="eyebrow">OUR PRIORITIES</span>
        <div className="industry-grid priority-grid">
          {priorities.map((s) => (
            <article className="industry-card" key={s.title}>
              <div className="industry-top">
                <s.icon size={34} strokeWidth={1.2} />
                <span>{s.label}</span>
              </div>
              <h2>{s.title}</h2>
              <p>{s.text}</p>
              <ul>
                {s.use.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
              <Link href={s.href}>
                {s.action}
                <ArrowUpRight size={15} />
              </Link>
            </article>
          ))}
        </div>
      </section>
      <section className="section potential-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">BEYOND THE INITIAL FOCUS</span>
            <h2>Potential markets.</h2>
          </div>
          <p>
            The same need to understand composites appears in other sectors.
            These are future opportunities, each requiring its own applicable
            physics and validation.
          </p>
        </div>
        <div className="potential-grid">
          {potential.map((s) => (
            <article key={s.title}>
              <s.icon size={27} strokeWidth={1.3} />
              <span className="tiny-label">POTENTIAL MARKET</span>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </article>
          ))}
        </div>
        <div className="industry-note">
          <p>
            The current product concept is a coupon-scale research workflow.
            Structural applications describe our direction; they are not
            existing component-level validation or certification.
          </p>
        </div>
      </section>
      <section className="section closing-section">
        <span className="eyebrow">BEGIN WITH THE ENGINEERING QUESTION</span>
        <div>
          <h2>
            What does your
            <br />
            material need to do?
          </h2>
          <Link className="button primary" href="/chat">
            Define a scope <ArrowUpRight size={17} />
          </Link>
        </div>
      </section>
    </main>
  );
}
