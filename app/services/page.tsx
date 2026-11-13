import Link from "next/link";
import { ArrowRight, BookOpen, Box, ClipboardList, FileText, Layers3, ScanLine, Wrench } from "lucide-react";
import { ClosingBand } from "@/components/closing-band";
import { MediaSlot } from "@/components/media-slot";
import { serviceHref, services, statusLabel, type Service } from "@/lib/services";
import "../inner-pages.css";
import "./services.css";

export const metadata = {
  title: "Services",
  description: "Computer-aided design, finite element modeling, test plans, documentation and manufacturing plans for composite coupons, from one coupon record.",
};

const icons: Record<Service["slug"], typeof Layers3> = {
  "computer-aided-design": Box,
  "finite-element-modeling": ScanLine,
  "test-plans": ClipboardList,
  documentation: FileText,
  "manufacturing-plans": Wrench,
};

/** The pictures the rows have; a row without one opens on its words (components/media-slot.tsx draws nothing without a file). */
const media: Partial<Record<Service["slug"], { label: string; src: string; alt: string }>> = {
  "test-plans": { label: "Coupon specimens before a tensile test", src: "/assets/images/coupon-01.jpg", alt: "A composite coupon specimen" },
  "manufacturing-plans": { label: "Woven carbon fiber", src: "/assets/images/carbon-weave.jpg", alt: "Woven carbon fiber" },
};

/** The services landing page (audit of 2026-10-31, item 13): one short summary per service, each leading to its page. */
export default function Services() {
  return (
    <main id="main" className="kit-page services-page">
      <section className="page-opening">
        <p className="page-opening-label">SERVICES / ONE COMPOSITE DEVELOPMENT WORKFLOW</p>
        <h1 className="page-opening-title">
          From an engineering question{" "}
          <br />
          to <em>a documented answer.</em>
        </h1>
        <div className="page-opening-grid">
          <div className="page-opening-copy">
            <p>
              Five ways to use the same platform: the geometry, the model, the test, the document and the plan for
              the shop, all from one coupon record.
            </p>
          </div>
          <div className="page-opening-note">
            <p className="page-opening-note-label">RESEARCH-FIRST PRODUCT</p>
            <p>
              Start with the material.
              <br />
              Follow the physics.
              <br />
              Check against the experiment.
            </p>
          </div>
        </div>
        <div className="page-opening-links">
          <Link href="/workspace/fea">
            <Layers3 size={24} strokeWidth={1.4} aria-hidden="true" />
            <div>
              <span>OPEN THE WORKSPACE</span>
              <span className="page-opening-link-title">Coupon analysis</span>
            </div>
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
          <Link href="/library">
            <BookOpen size={24} strokeWidth={1.4} aria-hidden="true" />
            <div>
              <span>OPEN THE LIBRARY</span>
              <span className="page-opening-link-title">Materials library</span>
            </div>
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </div>
      </section>
      <section className="band is-light service-list-band">
        <div className="band-head">
          <p className="band-label">THE FIVE SERVICES</p>
          <div className="band-statement">
            <h2>
              One record.
              <br />
              Five ways to use it.
            </h2>
            <p>
              A coupon described once feeds every service. The finite element model and the documentation are available,
              geometry and test plans in part, and manufacturing plans come later.
            </p>
          </div>
        </div>
        <div className="service-list">
          {services.map((service, i) => {
            const Icon = icons[service.slug];
            const picture = media[service.slug];
            return (
              <article className={picture ? "kit-row service-item has-media" : "kit-row service-item"} key={service.slug}>
                {picture ? <MediaSlot className="kit-row-head" label={picture.label} src={picture.src} alt={picture.alt} ratio="3/2" /> : null}
                <div className="kit-row-body service-item-body">
                  <div className="service-item-top">
                    <Icon size={22} strokeWidth={1.4} aria-hidden="true" />
                    <span className="kit-mono">0{i + 1} / {service.eyebrow}</span>
                    <span className={`kit-status kit-status-${service.status}`}>{statusLabel[service.status]}</span>
                  </div>
                  <h3>{service.title}</h3>
                  <p className="kit-text">{service.summary}</p>
                  <Link className="kit-link" href={serviceHref(service)}>
                    Read about {service.title.toLowerCase()} <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      </section>
      <ClosingBand
        label="ACCESS"
        heading={["The workspace is open", "to invited users."]}
        action={{ label: "Ask about access", href: "/contact" }}
      />
    </main>
  );
}
