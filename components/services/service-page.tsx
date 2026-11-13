import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, ArrowRight, ArrowUpRight } from "lucide-react";
import { findService, serviceHref, services, statusLabel, type Service } from "@/lib/services";

export type ServiceFact = { title: string; text: ReactNode };
export type ServiceLink = { label: string; href: string; primary?: boolean; external?: boolean };
export type ServicePageProps = {
  slug: string;
  /** The h1. An <em> marks its second phrase; the page opening sets it like the rest (app/inner-pages.css). */
  headline: ReactNode;
  lede: string;
  /** What the service does today, in facts the repository backs; for a planned service, what it would start from. */
  exists: ServiceFact[];
  /** What a visitor can see of the service at work, and what it hands over. A planned service has nothing to show, so its page
   * has no demonstration band; without `media` the band is only what it hands over, and is headed so. */
  demonstration?: { intro: string; media?: ReactNode; artefacts: string[]; note?: string };
  /** Work that does not exist yet; every entry is labelled PLANNED on the page. */
  planned?: ServiceFact[];
  access: { text: string; links: ServiceLink[] };
};

const statusText: Record<Service["status"], string> = {
  built: "Built. Open to the invited users of the closed beta.",
  partly: "Part of it exists today. The rest is listed under Planned.",
  planned: "No dates announced.",
};

type Band = "exists" | "demo" | "planned" | "access";

/** The shared shape of the five service pages (audit of 2026-10-31, item 14): the description and a demonstration
 * first, the access last. Each page passes its own facts; this component decides nothing about them. A planned service's page
 * says what it starts from instead of what exists, has no demonstration, and asks to be asked about (audit of 2026-11-12). */
export function ServicePage({ slug, headline, lede, exists, demonstration, planned = [], access }: ServicePageProps) {
  const service = findService(slug);
  if (!service) throw new Error(`No service is named ${slug}`);
  const index = services.indexOf(service);
  const previous = services[(index + services.length - 1) % services.length];
  const next = services[(index + 1) % services.length];
  const isPlanned = service.status === "planned";
  const demo = isPlanned ? undefined : demonstration;
  // The bands alternate, light first, whichever of them the page has.
  const bands: Band[] = ["exists", ...(demo ? (["demo"] as const) : []), ...(planned.length ? (["planned"] as const) : []), "access"];
  const tone = (band: Band) => (bands.indexOf(band) % 2 === 0 ? "band is-light" : "band");
  // Every heading names the service for a reader who lists the page's headings; the eye reads the slogan.
  const topic = <span className="kit-hidden">{service.title}: </span>;
  return (
    <main id="main" className="kit-page service-page">
      <section className="page-opening">
        <p className="page-opening-label">SERVICES / {service.title}</p>
        <h1 className="page-opening-title">
          {topic}
          {headline}
        </h1>
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
      <section className={`${tone("exists")} service-exists`}>
        <div className="band-head">
          <p className="band-label">{isPlanned ? "STARTS FROM" : "WHAT EXISTS TODAY"}</p>
          <div className="band-statement">
            <h2>
              {topic}
              {isPlanned ? "Built on the coupon record." : "What it does now."}
            </h2>
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
      {demo ? (
        <section className={`${tone("demo")} service-demo`}>
          <div className="band-head">
            <p className="band-label">{demo.media ? "DEMONSTRATION" : "WHAT YOU GET"}</p>
            <div className="band-statement">
              <h2>
                {topic}
                {demo.media ? "See it work." : "What you get."}
              </h2>
              <p>{demo.intro}</p>
            </div>
          </div>
          <div className={demo.media ? "band-grid" : "band-grid has-no-media"}>
            {demo.media ? <div className="service-demo-media">{demo.media}</div> : null}
            <div className="service-demo-list">
              {demo.media ? <span className="kit-mono">WHAT YOU GET</span> : null}
              <ul>
                {demo.artefacts.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {demo.note ? <p className="service-demo-note">{demo.note}</p> : null}
            </div>
          </div>
        </section>
      ) : null}
      {planned.length ? (
        <section className={`${tone("planned")} service-planned`}>
          <div className="band-head">
            <p className="band-label">PLANNED</p>
            <div className="band-statement">
              <h2>
                {topic}
                What comes next.
              </h2>
            </div>
          </div>
          <div className="band-grid">
            <div className="service-planned-list" data-count={planned.length}>
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
      <section className={`${tone("access")} service-access`} id="access">
        <div className="band-head">
          <p className="band-label">ACCESS</p>
          <div className="band-statement">
            <h2>
              {topic}
              {isPlanned ? "Ask about it." : "Use it."}
            </h2>
            <p>{access.text}</p>
            <div className="service-access-links">
              {access.links.map((link) =>
                link.external ? (
                  <a key={link.href} className={link.primary ? "button primary" : "kit-link"} href={link.href} target="_blank" rel="noopener noreferrer">
                    {link.label} <ArrowUpRight size={16} aria-hidden="true" />
                    <span className="kit-hidden"> (opens in a new tab)</span>
                  </a>
                ) : (
                  <Link key={link.href} className={link.primary ? "button primary" : "kit-link"} href={link.href}>
                    {link.label} <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                ),
              )}
            </div>
          </div>
        </div>
      </section>
      <nav className="service-nav" aria-label="Other services">
        <Link href={serviceHref(previous)} aria-label={`Previous service: ${previous.title}`}>
          <ArrowLeft size={16} aria-hidden="true" /> {previous.title}
        </Link>
        <Link href="/services">All services</Link>
        <Link href={serviceHref(next)} aria-label={`Next service: ${next.title}`}>
          {next.title} <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </nav>
    </main>
  );
}
