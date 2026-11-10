import { existsSync } from "node:fs";
import { join } from "node:path";
import Link from "next/link";
import { ArrowUpRight, MoveUpRight } from "lucide-react";
import { ClosingBand } from "@/components/closing-band";
import { HeroVideoKeeper } from "@/components/home/hero-video-keeper";
import { LaminateHero } from "@/components/home/laminate-hero";
import { serviceHref, services, statusLabel } from "@/lib/services";
import { team } from "@/lib/team";
import "./home.css";

/** The hero clip's web copy (ADR-0069), written by scripts/hero-video.sh into the git-ignored public/media. A build without it,
 * such as one from the public repository, shows the still photo instead. */
const heroVideo = existsSync(join(process.cwd(), "public", "media", "hero.mp4"));
// Plain HTML so the browser sees "muted" before React runs, which autoplay requires; visitors who ask for reduced motion get no
// source, so the poster frame stays.
const heroVideoHtml =
  '<video autoplay muted loop playsinline preload="auto" poster="/media/hero.jpg" disablepictureinpicture tabindex="-1">' +
  '<source src="/media/hero.mp4" type="video/mp4" media="(prefers-reduced-motion: no-preference)"></video>';

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

/** The home page: the hero first, the laminate calculator under it as the demonstration (ADR-0076, ADR-0077),
 * then short blurbs on the mission, the platform, the evidence, the team and what is new. The workflow and the roadmap live
 * on About. */
export default function Home() {
  return (
    <main id="main">
      <section className="home-hero" id="overview" aria-labelledby="home-hero-title">
        <div className={heroVideo ? "home-hero-media has-video" : "home-hero-media"} aria-hidden="true">
          {heroVideo ? <div className="home-hero-video" dangerouslySetInnerHTML={{ __html: heroVideoHtml }} /> : null}
          {heroVideo ? <HeroVideoKeeper /> : null}
        </div>
        {/* The lens (ADR-0071) is hidden for now at the lead's request (amendment 1); `<HeroLens />` from components/home/hero-lens.tsx brings it back. */}
        <div className="home-hero-grid">
          <h1 className="home-hero-title" id="home-hero-title">
            Composites.
            <br />
            Calculated.
          </h1>
          <div className="home-hero-copy">
            <p>
              We&apos;re bringing composite theory and real test data into one engineering platform, changing how laminates
              and coupons are set up, analyzed and documented.
            </p>
            <p>
              Spend less time on setup and reports. Spend more time on the structure. Trace every number back to its source.
            </p>
          </div>
        </div>
      </section>
      <LaminateHero apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
      {/* The sections under the demo are bands of the section kit (app/sections.css, ADR-0077 amendment 11), dark and light in
          turn. Each opens with the kit's head; what follows starts at column 4, under the statement. The four principles close
          the Mission band as a strip. */}
      <section className="band home-blurb home-mission" id="mission">
        <div className="band-head">
          <p className="band-label">01 / MISSION</p>
          <div className="band-statement">
            <h2>One record, from the layup to the test.</h2>
            <p>
              Composite structures are designed, analyzed, tested and built by different people with different tools, and the
              evidence gets lost between them. Anisotropy keeps those steps on one record, grounded in composite theory and
              real mechanical test data, so every answer comes with its assumptions and references.
            </p>
            <Link className="home-link" href="/about">
              What we are building <ArrowUpRight size={16} />
            </Link>
          </div>
        </div>
        <ul className="home-principles">
          <li>PHYSICS AT THE CORE</li>
          <li>LAB DATA AS THE FOUNDATION</li>
          <li>RESEARCH BEFORE ASSUMPTIONS</li>
          <li>
            <span>
              EVERY RESULT, TRACEABLE <MoveUpRight size={15} />
            </span>
          </li>
        </ul>
      </section>
      <section className="band is-light home-blurb home-platform" id="platform">
        <div className="band-head">
          <p className="band-label">02 / PLATFORM</p>
          <div className="band-statement">
            <h2>Five ways to use it.</h2>
            <p>
              The same coupon record feeds every service. Two are built, two exist in part, one is stated as planned; each
              page says which.
            </p>
          </div>
        </div>
        <div className="band-grid">
          <div className="home-cards home-platform-grid">
            {services.map((service) => (
              <article className="band-card" key={service.slug}>
                <div className="home-card-top">
                  <span className="home-tag">{service.eyebrow}</span>
                  <span className={`home-tag home-status home-status-${service.status}`}>{statusLabel[service.status]}</span>
                </div>
                <h3>{service.title}</h3>
                <p>{service.summary}</p>
                <Link className="home-link" href={serviceHref(service)}>
                  The page <ArrowUpRight size={16} />
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>
      <section className="band home-blurb research-foundation" id="impact">
        <div className="band-head">
          <p className="band-label">03 / IMPACT</p>
          <div className="band-statement">
            <h2>Knowledge worth building on.</h2>
            <p>
              Research comes first. Explore a growing foundation of reviewed open-source datasets, data from published
              research studies, and evidence generated in our own lab.
            </p>
          </div>
        </div>
        <div className="band-grid">
          <div className="home-cards home-evidence-grid">
            <article className="band-card">
              <div className="home-card-top">
                <span className="home-tag">01 / EVERY NUMBER, A RECORD</span>
              </div>
              <h3>Trace it back.</h3>
              <p>
                Each calculation and each coupon job leaves a run record with its inputs, the engine version and the result,
                so a number in a report can be followed to the run that produced it.
              </p>
            </article>
            <article className="band-card">
              <div className="home-card-top">
                <span className="home-tag">02 / CHECKED AGAINST A REFERENCE</span>
              </div>
              <h3>Compared, not assumed.</h3>
              <p>
                Our first bending coupon, IM7/8552 in ASTM D7264 proportions, against CalculiX S8R: 100 numbers within 3&nbsp;%,
                the nose reaction within 0.12&nbsp;%. The decks and the record are in the repository.
              </p>
            </article>
            <article className="band-card">
              <div className="home-card-top">
                <span className="home-tag">03 / THE MATERIALS LIBRARY</span>
              </div>
              <h3>Keep the evidence close.</h3>
              <p>
                Source records for carbon, glass and sandwich cores, each value with its page and unit, alongside the
                governing equations and topic-by-topic explanations.
              </p>
              <Link className="home-link" href="/library">
                Explore the materials library <ArrowUpRight size={16} />
              </Link>
            </article>
          </div>
        </div>
      </section>
      <section className="band is-light home-blurb home-team" id="working">
        <div className="band-head">
          <p className="band-label">04 / WORKING AT ANISOTROPY</p>
          <div className="band-statement">
            <h2>Five people, two seats each.</h2>
            <p>
              One technical seat and one for the company per person. A lead decides alone inside the seat; anything that
              could alter results, cost, security, test plans or spending goes to the CEO. The repository is public, the
              decisions and their reasons with it.
            </p>
          </div>
        </div>
        <div className="band-grid">
          <div className="home-cards home-team-grid">
            {team.map((person) => (
              <article className="band-card" key={person.name}>
                <h3>{person.name}</h3>
                <p>
                  {person.role ? `${person.role}. ` : ""}
                  {person.technical.charAt(0).toUpperCase() + person.technical.slice(1)}
                  {person.company ? `; ${person.company}` : ""}.
                </p>
              </article>
            ))}
            <Link className="home-link" href="/about#team">
              The team on the About page <ArrowUpRight size={16} />
            </Link>
          </div>
        </div>
      </section>
      <section className="band home-blurb" id="news">
        <div className="band-head">
          <p className="band-label">05 / WHAT IS NEW</p>
          <div className="band-statement">
            <h2>Lately.</h2>
            <p>
              Three recent changes, as the changelog records them. What was validated against what, and what is still
              planned, is written there too.
            </p>
          </div>
        </div>
        <div className="home-news">
          {news.map((item) => (
            <article key={item.title}>
              <span className="home-tag">{item.when.toUpperCase()}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
      <ClosingBand
        label="THE NEXT LAYER STARTS WITH A QUESTION."
        heading={["Let’s define what", "comes next."]}
        action={{ label: "Start a conversation", href: "/workspace/fea" }}
        links={{
          label: "EXPLORE THE RESEARCH",
          items: [
            { label: "Materials & physics library", href: "/library" },
            { label: "Our research approach", href: "/about" },
          ],
        }}
      />
    </main>
  );
}
