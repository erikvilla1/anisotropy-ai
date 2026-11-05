import Link from "next/link";
import { ArrowUpRight, BookOpen, Box, ClipboardList, FileText, Layers3, ScanLine, Wrench } from "lucide-react";
import { MediaSlot } from "@/components/media-slot";
import { serviceHref, services, statusLabel, type Service } from "@/lib/services";
import "./services.css";

export const metadata = {
  title: "Services — Anisotropy",
  description: "Computer-aided design, finite element modeling, test plans, documentation and manufacturing plans for composite coupons, each on its own page.",
};

const icons: Record<Service["slug"], typeof Layers3> = {
  "computer-aided-design": Box,
  "finite-element-modeling": ScanLine,
  "test-plans": ClipboardList,
  documentation: FileText,
  "manufacturing-plans": Wrench,
};

const media: Record<Service["slug"], { label: string; src?: string; alt?: string }> = {
  "computer-aided-design": { label: "The studio's mesh of an open-hole coupon" },
  "finite-element-modeling": { label: "A solved coupon in the studio: the first ply to fail" },
  "test-plans": { label: "Coupon specimens before a tensile test", src: "/assets/images/coupon-01.jpg", alt: "A composite coupon specimen" },
  documentation: { label: "Pages of a coupon package: model chapter and comparison table" },
  "manufacturing-plans": { label: "Laying up a coupon panel", src: "/assets/images/carbon-weave.jpg", alt: "Woven carbon fiber" },
};

/** The services landing page (audit of 2026-10-31, item 13): one short summary per service, each leading to its page. */
export default function Services() {
  return (
    <main id="main" className="inner-page services-page">
      <section className="section page-intro">
        <span className="eyebrow">
          SERVICES / ONE COMPOSITE DEVELOPMENT WORKFLOW
        </span>
        <div className="intro-grid">
          <div>
            <h1>
              From an engineering question
              <br />
              to <em>a documented answer.</em>
            </h1>
            <p>
              Five ways to use the same platform: the geometry, the model, the test, the document and the plan for
              the shop, all from one coupon record. Each page says what exists today and what is planned.
            </p>
          </div>
          <div className="intro-aside">
            <span className="status-dot" />
            <span>RESEARCH-FIRST PRODUCT</span>
            <p>
              Start with the material.
              <br />
              Follow the physics.
              <br />
              Check against the experiment.
            </p>
          </div>
        </div>
        <div className="service-selectors">
          <Link href="/chat">
            <Layers3 size={23} />
            <div>
              <span>TRY THE EXPERIENCE</span>
              <h3>Development Process Streamlining</h3>
            </div>
            <ArrowUpRight size={18} />
          </Link>
          <Link href="/library">
            <BookOpen size={23} />
            <div>
              <span>EXPLORE THE FOUNDATION</span>
              <h3>Materials & Physics Library</h3>
            </div>
            <ArrowUpRight size={18} />
          </Link>
        </div>
      </section>
      <section className="section service-grid-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">THE FIVE SERVICES</span>
            <h2>
              One record.
              <br />
              Five ways to use it.
            </h2>
          </div>
          <p>
            A coupon described once feeds every service. The finite element model and the documentation are built;
            geometry and test plans exist in part; manufacturing plans are stated as planned.
          </p>
        </div>
        <div className="service-grid">
          {services.map((service, i) => {
            const Icon = icons[service.slug];
            const picture = media[service.slug];
            return (
              <article className="service-card" key={service.slug}>
                <MediaSlot label={picture.label} src={picture.src} alt={picture.alt} ratio="3/2" />
                <div className="service-card-body">
                  <div className="service-card-top">
                    <Icon size={22} strokeWidth={1.4} />
                    <span className="tiny-label">0{i + 1} / {service.eyebrow}</span>
                    <span className={`service-status service-status-${service.status}`}>{statusLabel[service.status]}</span>
                  </div>
                  <h3>{service.title}</h3>
                  <p>{service.summary}</p>
                  <Link className="text-button" href={serviceHref(service)}>
                    Read about {service.title.toLowerCase()} <ArrowUpRight size={15} />
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      </section>
      <section className="section service-preview-note">
        <p>
          The studio, the materials library and the calculator are interactive today. Every page under Services
          names its planned parts as planned, without a date.
        </p>
        <Link href="/contact">
          Ask about access <ArrowUpRight size={15} />
        </Link>
      </section>
    </main>
  );
}
