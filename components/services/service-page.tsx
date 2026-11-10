import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, ArrowRight, ArrowUpRight } from "lucide-react";
import { findService, serviceHref, services, statusLabel, type Service } from "@/lib/services";

export type ServiceFact = { title: string; text: string };
export type ServiceLink = { label: string; href: string; primary?: boolean; external?: boolean };
export type ServicePageProps = {
  slug: string;
  /** The h1. An <em> marks its second phrase; the page opening sets it like the rest (app/inner-pages.css). */
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
export function ServicePage({ slug, headline, lede, exists, demonstration, planned = [], access }: ServicePageProps) {
  const service = findService(slug);
  if (!service) throw new Error(`No service is named ${slug}`);
  const index = services.indexOf(service);
  const previous = services[(index + services.length - 1) % services.length];
  const next = services[(index + 1) % services.length];
  const hasPlanned = planned.length > 0;
  return (
    <main id="main" className="kit-page service-page">
      <section className="page-opening">
        <p className="page-opening-label">SERVICES / {service.eyebrow}</p>
        <h1 className="page-opening-title">{headline}</h1>
        <div className="page-opening-grid">
          <div className="page-opening-copy">
            <p>{lede}</p>
          </div>
          <div className="page-opening-note">
            <p className={`page-opening-note-label is-${service.status}`}>{statusLabel[service.status]}</p>
            <p>{statusText[service.status]}</p>
          </div>
        </div>
      </section>
      <section className="band is-light service-exists">
        <div className="band-head">
          <p className="band-label">WHAT EXISTS TODAY</p>
          <div className="band-statement">
            <h2>What it does now.</h2>
          </div>
        </div>
        <div className="service-facts">
          {exists.map((fact, i) => (
            <article className="kit-row" key={fact.title}>
              <div className="kit-row-head service-fact-head">
                <span className="kit-mono">0{i + 1}</span>
                <h3 className="kit-title">{fact.title}</h3>
              </div>
              <p className="kit-row-body kit-text">{fact.text}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="band service-demo">
        <div className="band-head">
          <p className="band-label">DEMONSTRATION</p>
          <div className="band-statement">
            <h2>See it work.</h2>
            <p>{demonstration.intro}</p>
          </div>
        </div>
        <div className="band-grid">
          <div className="service-demo-media">{demonstration.media}</div>
          <div className="service-demo-list">
            <span className="kit-mono">WHAT YOU GET</span>
            <ul>
              {demonstration.artefacts.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            {demonstration.note ? <p className="service-demo-note">{demonstration.note}</p> : null}
          </div>
        </div>
      </section>
      {hasPlanned ? (
        <section className="band is-light service-planned">
          <div className="band-head">
            <p className="band-label">PLANNED</p>
            <div className="band-statement">
              <h2>What comes next.</h2>
              <p>Listed so the site claims nothing that does not exist. Dates are not announced.</p>
            </div>
          </div>
          <div className="band-grid">
            <div className="service-planned-list">
              {planned.map((fact) => (
                <article className="band-card service-planned-card" key={fact.title}>
                  <span className="kit-badge">PLANNED</span>
                  <h3 className="kit-title">{fact.title}</h3>
                  <p>{fact.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      ) : null}
      {/* The bands alternate, light first: with a Planned band before it this one is dark, without one it is light. */}
      <section className={hasPlanned ? "band service-access" : "band is-light service-access"} id="access">
        <div className="band-head">
          <p className="band-label">ACCESS</p>
          <div className="band-statement">
            <h2>Use it.</h2>
            <p>{access.text}</p>
            <div className="service-access-links">
              {access.links.map((link) =>
                link.external ? (
                  <a key={link.href} className={link.primary ? "button primary" : "kit-link"} href={link.href} target="_blank" rel="noreferrer">
                    {link.label} <ArrowUpRight size={16} />
                  </a>
                ) : (
                  <Link key={link.href} className={link.primary ? "button primary" : "kit-link"} href={link.href}>
                    {link.label} <ArrowUpRight size={16} />
                  </Link>
                ),
              )}
            </div>
          </div>
        </div>
      </section>
      <nav className="service-nav" aria-label="Other services">
        <Link href={serviceHref(previous)}>
          <ArrowLeft size={16} /> {previous.title}
        </Link>
        <Link href="/services">All services</Link>
        <Link href={serviceHref(next)}>
          {next.title} <ArrowRight size={16} />
        </Link>
      </nav>
    </main>
  );
}
