import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, ArrowRight, ArrowUpRight } from "lucide-react";
import { findService, serviceHref, services, statusLabel, type Service } from "@/lib/services";

export type ServiceFact = { title: string; text: string };
export type ServiceLink = { label: string; href: string; primary?: boolean; external?: boolean };
export type ServicePageProps = {
  slug: string;
  /** The h1, with an <em> on the part to colour. */
  headline: ReactNode;
  lede: string;
  /** What the service does today, in facts the repository backs. */
  exists: ServiceFact[];
  demonstration: { intro: string; media: ReactNode; artefacts: string[]; note?: string };
  /** Work that does not exist yet; every entry is labelled PLANNED on the page. */
  planned?: ServiceFact[];
  access: { text: string; links: ServiceLink[] };
};

const statusText: Record<Service["status"], string> = {
  built: "Built. Open to the invited users of the closed beta.",
  partly: "Part of it exists today. The rest is listed under Planned.",
  planned: "Not built yet. This page says what is intended.",
};

/** The shared shape of the five service pages (audit of 2026-10-31, item 14): the description and a demonstration
 * first, the access last. Each page passes its own facts; this component decides nothing about them. */
export function ServicePage({ slug, headline, lede, exists, demonstration, planned, access }: ServicePageProps) {
  const service = findService(slug);
  if (!service) throw new Error(`No service is named ${slug}`);
  const index = services.indexOf(service);
  const previous = services[(index + services.length - 1) % services.length];
  const next = services[(index + 1) % services.length];
  return (
    <main id="main" className="inner-page service-page">
      <section className="section page-intro">
        <span className="eyebrow">SERVICES / {service.eyebrow}</span>
        <div className="intro-grid">
          <div>
            <h1>{headline}</h1>
            <p>{lede}</p>
          </div>
          <div className="intro-aside">
            <span className="status-dot" />
            <span>{statusLabel[service.status]}</span>
            <p>{statusText[service.status]}</p>
          </div>
        </div>
      </section>
      <section className="section service-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">WHAT EXISTS TODAY</span>
            <h2>What it does now.</h2>
          </div>
        </div>
        <div className="service-facts">
          {exists.map((fact, i) => (
            <article key={fact.title}>
              <span className="tiny-label">0{i + 1}</span>
              <h3>{fact.title}</h3>
              <p>{fact.text}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="section service-section service-demo">
        <div className="section-heading">
          <div>
            <span className="eyebrow">DEMONSTRATION</span>
            <h2>See it work.</h2>
          </div>
          <p>{demonstration.intro}</p>
        </div>
        <div className="service-demo-grid">
          <div className="service-demo-media">{demonstration.media}</div>
          <div className="service-demo-list">
            <span className="tiny-label">WHAT YOU GET</span>
            <ul>
              {demonstration.artefacts.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            {demonstration.note ? <p className="service-demo-note">{demonstration.note}</p> : null}
          </div>
        </div>
      </section>
      {planned && planned.length > 0 ? (
        <section className="section service-section service-planned">
          <div className="section-heading">
            <div>
              <span className="eyebrow">PLANNED</span>
              <h2>What comes next.</h2>
            </div>
            <p>Listed so the site claims nothing that does not exist. Dates are not announced.</p>
          </div>
          <div className="service-facts">
            {planned.map((fact) => (
              <article key={fact.title}>
                <span className="sample-badge">PLANNED</span>
                <h3>{fact.title}</h3>
                <p>{fact.text}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      <section className="section service-access" id="access">
        <div>
          <span className="eyebrow">ACCESS</span>
          <h2>Use it.</h2>
          <p>{access.text}</p>
        </div>
        <div className="service-access-links">
          {access.links.map((link) =>
            link.external ? (
              <a key={link.href} className={link.primary ? "button primary" : "text-button"} href={link.href} target="_blank" rel="noreferrer">
                {link.label} <ArrowUpRight size={16} />
              </a>
            ) : (
              <Link key={link.href} className={link.primary ? "button primary" : "text-button"} href={link.href}>
                {link.label} <ArrowUpRight size={16} />
              </Link>
            ),
          )}
        </div>
      </section>
      <nav className="section service-nav" aria-label="Other services">
        <Link href={serviceHref(previous)}>
          <ArrowLeft size={15} /> {previous.title}
        </Link>
        <Link href="/services">All services</Link>
        <Link href={serviceHref(next)}>
          {next.title} <ArrowRight size={15} />
        </Link>
      </nav>
    </main>
  );
}
