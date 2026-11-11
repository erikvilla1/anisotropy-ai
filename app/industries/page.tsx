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
import { ClosingBand } from "@/components/closing-band";
import { MediaSlot } from "@/components/media-slot";
import "../inner-pages.css";
export const metadata = { title: "Industries — Anisotropy" };
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
    href: "/workspace/fea",
    action: "Define an aerospace research scope",
    media: { label: "A composite aerostructure or a coupon cut from one", kind: "image" as const },
  },
  {
    icon: GraduationCap,
    title: "Research & education",
    label: "PRIORITY APPLICATION",
    text: "A composites material library and detailed engineering explanations for the people investigating, teaching, and learning how laminates behave.",
    use: [
      "Source-linked material properties and thicknesses",
      "CLT, local stresses, and failure criteria by topic",
      "Reproducible research and step-by-step methods",
    ],
    href: "/library",
    action: "Explore the materials & physics library",
    media: {
      label: "Microscopy of a tested coupon",
      kind: "image" as const,
      src: "/assets/images/microscopy.jpg",
      alt: "Microscopy image of a composite specimen",
    },
  },
];
const potential = [
  {
    icon: Wind,
    title: "Wind & energy",
    text: "Future laminate, blade, and repair studies grounded in relevant material and test evidence.",
    media: "A blade section or a glass laminate panel",
  },
  {
    icon: Car,
    title: "Automotive & mobility",
    text: "Potential lightweight material screening and stiffness-to-mass trade studies.",
    media: "A carbon body panel or chassis member",
  },
  {
    icon: Ship,
    title: "Marine",
    text: "Potential applications in composite panels, environmental conditioning, and repair assessment.",
    media: "A hull panel or a conditioned coupon",
  },
  {
    icon: Factory,
    title: "Advanced manufacturing",
    text: "Future process-to-property studies linking fabrication conditions to measured behavior.",
    media: "A layup or cure in progress",
  },
];
export default function Industries() {
  return (
    <main id="main" className="kit-page industries-page">
      <section className="page-opening">
        <p className="page-opening-label">INDUSTRIES / A FOCUSED START</p>
        <h1 className="page-opening-title">
          Built for research.
          <br />
          <em>Directed toward flight.</em>
        </h1>
        <div className="page-opening-grid">
          <div className="page-opening-copy">
            <p>
              Aerospace is our primary industry. Research and education are
              immediate priorities, with a composites material library at the
              center of the experience.
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
      <section className="band is-light industry-priorities-band">
        <div className="band-head is-label-only">
          <p className="band-label">OUR PRIORITIES</p>
        </div>
        <div className="industry-priorities">
          {priorities.map((s) => (
            <article className="industry-priority" key={s.title}>
              <MediaSlot label={s.media.label} kind={s.media.kind} src={s.media.src} alt={s.media.alt} ratio="16/9" />
              <div className="industry-priority-body">
                <div className="industry-priority-top">
                  <s.icon size={32} strokeWidth={1.2} />
                  <span className="kit-mono">{s.label}</span>
                </div>
                <h2>{s.title}</h2>
                <p className="kit-text">{s.text}</p>
                <ul className="industry-uses">
                  {s.use.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
                <Link className="kit-link" href={s.href}>
                  {s.action}
                  <ArrowUpRight size={16} />
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="band industry-potentials-band">
        <div className="band-head">
          <p className="band-label">BEYOND THE INITIAL FOCUS</p>
          <div className="band-statement">
            <h2>Potential industries.</h2>
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
              <MediaSlot label={s.media} kind="clip" ratio="16/9" />
              <div className="industry-potential-body">
                <s.icon size={26} strokeWidth={1.3} />
                <span className="kit-mono">POTENTIAL INDUSTRY</span>
                <h3 className="kit-title">{s.title}</h3>
                <p>{s.text}</p>
              </div>
            </article>
          ))}
        </div>
        <div className="kit-note">
          <p className="kit-note-text">
            The current product concept is a coupon-scale research workflow.
            Structural applications describe our direction; they are not
            existing component-level validation or certification.
          </p>
        </div>
      </section>
      <ClosingBand
        label="BEGIN WITH THE ENGINEERING QUESTION"
        heading={["What does your", "material need to do?"]}
        action={{ label: "Define a scope", href: "/workspace/fea" }}
      />
    </main>
  );
}
