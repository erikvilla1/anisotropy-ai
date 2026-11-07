import Link from "next/link";
import { ArrowDown, ArrowUpRight, MoveUpRight } from "lucide-react";
import { HomeComposer } from "@/components/home-composer";
import { HeroLens } from "@/components/home/hero-lens";
import { LaminateHero } from "@/components/home/laminate-hero";
import { serviceHref, services, statusLabel } from "@/lib/services";
import { team } from "@/lib/team";
import "./home.css";

/** What shipped lately, in words a visitor can check against the changelog; no number without a record behind it. */
const news = [
  {
    when: "November 2026",
    title: "The hosted closed beta",
    text: "The studio runs at anisotropy.dev for an invite list, with its outputs kept and every run recorded. Accounts for everyone else are not open yet.",
  },
  {
    when: "October 2026",
    title: "Bending coupons and plates",
    text: "Three- and four-point bending in our own shell element, checked against CalculiX, and a plate kind held and loaded on regions you name.",
  },
  {
    when: "October 2026",
    title: "The studio opens on a chat",
    text: "Describe a coupon test in a sentence; the chat fills the same rows the form holds, checks the setup and runs it.",
  },
];

/** The home page: the hero with the chat block first, the laminate calculator under it as the demonstration (ADR-0065),
 * then short blurbs on the mission, the platform, the evidence, the team and what is new. The workflow and the roadmap live
 * on About. */
export default function Home() {
  return (
    <main id="main">
      <section className="home-hero" id="overview" aria-labelledby="home-hero-title">
        <div className="home-hero-media" />
        <div className="home-hero-grid">
          <div className="home-hero-title">
            <span className="eyebrow">
              <span className="status-dot" /> ENGINEERING INTELLIGENCE, GROUNDED IN EVIDENCE
            </span>
            <h1 id="home-hero-title">
              From material
              <br />
              to <span>understanding.</span>
            </h1>
          </div>
          <figure className="home-hero-lens">
            <div className="home-hero-lens-frame" aria-hidden="true">
              <HeroLens />
            </div>
            <figcaption>
              CARBON FIBER
              <br />
              <span>The material is the starting point.</span>
            </figcaption>
          </figure>
          <div className="home-hero-copy">
            <p>A clearer path from composite coupon to confident design.</p>
            <p>Connecting physics, physical testing, and research—one layer at a time.</p>
            <HomeComposer />
            <p className="home-hero-footnote">
              <span className="home-hero-rule" />
              COUPONS FIRST. EVIDENCE ALWAYS.
            </p>
          </div>
        </div>
        <div className="home-hero-bottom">
          <span>01 — THE FIRST CHAPTER</span>
          <a href="#laminate">
            SCROLL TO DISCOVER <ArrowDown size={13} />
          </a>
          <span>BUILT TO BE TESTED.</span>
        </div>
      </section>
      <LaminateHero apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
      <div className="principles-strip">
        <span>
          <span className="status-dot" /> PHYSICS AT THE CORE
        </span>
        <span>LAB DATA AS THE FOUNDATION</span>
        <span>RESEARCH BEFORE ASSUMPTIONS</span>
        <span>
          EVERY RESULT, TRACEABLE <MoveUpRight size={15} />
        </span>
      </div>
      <section className="section home-blurb home-mission" id="mission">
        <div className="section-heading">
          <div>
            <span className="eyebrow">01 / MISSION</span>
            <h2>
              One record,
              <br />
              from the layup to the test.
            </h2>
          </div>
        </div>
        <p className="lead">
          Composite structures are designed, analyzed, tested and built by different people with different tools, and the
          evidence gets lost between them. Anisotropy keeps those steps on one record, grounded in composite theory and
          real mechanical test data, so every answer comes with its assumptions and references.
        </p>
        <Link className="text-button" href="/about">
          What we are building <ArrowUpRight size={15} />
        </Link>
      </section>
      <section className="section home-blurb home-platform" id="platform">
        <div className="section-heading">
          <div>
            <span className="eyebrow">02 / PLATFORM</span>
            <h2>
              Five ways
              <br />
              to use it.
            </h2>
          </div>
          <p>
            The same coupon record feeds every service. Two are built, two exist in part, one is stated as planned; each
            page says which.
          </p>
        </div>
        <div className="home-platform-grid">
          {services.map((service) => (
            <article key={service.slug}>
              <div>
                <span className="tiny-label">{service.eyebrow}</span>
                <span className={`service-status service-status-${service.status}`}>{statusLabel[service.status]}</span>
              </div>
              <h3>{service.title}</h3>
              <p>{service.summary}</p>
              <Link href={serviceHref(service)}>
                The page <ArrowUpRight size={13} />
              </Link>
            </article>
          ))}
        </div>
      </section>
      <section className="section home-blurb research-foundation" id="impact">
        <div className="section-heading">
          <div>
            <span className="eyebrow">03 / IMPACT</span>
            <h2>
              Knowledge worth
              <br />
              building on.
            </h2>
          </div>
          <p>
            Research comes first. Explore a growing foundation of reviewed open-source datasets, data from published
            research studies, and evidence generated in our own lab.
          </p>
        </div>
        <div className="evidence-grid">
          <article>
            <span>01 / EVERY NUMBER, A RECORD</span>
            <h3>Trace it back.</h3>
            <p>
              Each calculation and each coupon job leaves a run record with its inputs, the engine version and the result,
              so a number in a report can be followed to the run that produced it.
            </p>
          </article>
          <article>
            <span>02 / CHECKED AGAINST A REFERENCE</span>
            <h3>Compared, not assumed.</h3>
            <p>
              Our first bending coupon, IM7/8552 in ASTM D7264 proportions, against CalculiX S8R: 100 numbers within 3 %,
              the nose reaction within 0.12 %. The decks and the record are in the repository.
            </p>
          </article>
          <article className="evidence-library">
            <span>03 / THE MATERIALS LIBRARY</span>
            <h3>Keep the evidence close.</h3>
            <p>
              Source records for carbon, glass and sandwich cores, each value with its page and unit, alongside the
              governing equations and topic-by-topic explanations.
            </p>
            <Link className="text-button" href="/library">
              Explore the materials library <ArrowUpRight size={16} />
            </Link>
          </article>
        </div>
      </section>
      <section className="section home-blurb home-team" id="working">
        <div className="section-heading">
          <div>
            <span className="eyebrow">04 / WORKING AT ANISOTROPY</span>
            <h2>
              Five people,
              <br />
              two seats each.
            </h2>
          </div>
          <p>
            One technical seat and one for the company per person. A lead decides alone inside the seat; anything that
            could alter results, cost, security, test plans or spending goes to the CEO. The repository is public, the
            decisions and their reasons with it.
          </p>
        </div>
        <div className="home-team-grid">
          {team.map((person) => (
            <article key={person.name}>
              <h3>{person.name}</h3>
              <p>
                {person.role ? `${person.role}. ` : ""}
                {person.technical.charAt(0).toUpperCase() + person.technical.slice(1)}
                {person.company ? `; ${person.company}` : ""}.
              </p>
            </article>
          ))}
        </div>
        <Link className="text-button" href="/about#team">
          The team on the About page <ArrowUpRight size={15} />
        </Link>
      </section>
      <section className="section home-blurb" id="news">
        <div className="section-heading">
          <div>
            <span className="eyebrow">05 / WHAT IS NEW</span>
            <h2>Lately.</h2>
          </div>
          <p>Three recent changes, as the changelog records them. What was validated against what, and what is still planned, is written there too.</p>
        </div>
        <div className="home-news">
          {news.map((item) => (
            <article key={item.title}>
              <span className="tiny-label">{item.when.toUpperCase()}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="closing-section section">
        <span className="eyebrow">THE NEXT LAYER STARTS WITH A QUESTION.</span>
        <div>
          <h2>
            Let’s define what
            <br />
            comes next.
          </h2>
          <Link className="button primary" href="/workspace/fea">
            Start a conversation <ArrowUpRight size={18} />
          </Link>
        </div>
        <div className="document-links">
          <span>EXPLORE THE RESEARCH</span>
          <Link href="/library">
            Materials & physics library <ArrowUpRight size={15} />
          </Link>
          <Link href="/about">
            Our research approach <ArrowUpRight size={15} />
          </Link>
        </div>
      </section>
    </main>
  );
}
