import { existsSync } from "node:fs";
import { join } from "node:path";
import Link from "next/link";
import { ArrowUpRight, MoveUpRight } from "lucide-react";
import { ClosingBand } from "@/components/closing-band";
import { HeroOutro } from "@/components/home/hero-outro";
import { ProductDemo } from "@/components/home/product-demo";
import { ScrollToExplore } from "@/components/home/scroll-to-explore";
import { HeroVideoKeeper } from "@/components/home/hero-video-keeper";
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

/** The home page: the hero first (ADR-0076, ADR-0077), a scroll-driven tour of one calculation (ADR-0084), the laminate
 * calculator as the demonstration, then bands on the mission, the platform, the team and what is new, and the closing
 * band. The workflow and the roadmap live on About. */
/** LinkedIn's "in", as letters only: the round ground is the badge's own (app/home.css, .home-face-in). */
function LinkedInMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zM7.119 20.452H3.555V9h3.564v11.452z" />
    </svg>
  );
}

export default function Home() {
  return (
    <main id="main">
      <section className="home-hero" id="overview" aria-labelledby="home-hero-title">
        <div className={heroVideo ? "home-hero-media has-video" : "home-hero-media"} aria-hidden="true">
          {heroVideo ? <div className="home-hero-video" dangerouslySetInnerHTML={{ __html: heroVideoHtml }} /> : null}
          {heroVideo ? <HeroVideoKeeper /> : null}
        </div>
        {/* The lens (ADR-0071) is hidden for now at the lead's request (amendment 1); `<HeroLens />` from components/home/hero-lens.tsx brings it back. */}
        {/* The words, in Anduril's arrangement (ADR-0077 amendments 19 and 27): one statement in large capitals in the middle,
            and under it a row of the year, the mark and the name. The load-in (ADR-0070 amendments 1 and 4) types
            the statement and the small lines in, and a text cursor blinks at the statement's end (components/intro-text.ts). */}
        <div className="home-hero-stack">
          <h1 className="home-hero-title" id="home-hero-title" data-intro="type" data-outro="type" data-intro-caret="">
            one engineering platform
            <br />
            for composite theory
            <br />
            and real test data
            <span className="type-caret" aria-hidden="true" />
          </h1>
          <div className="home-hero-row">
            {/* The row of ADR-0077 amendment 28: the year on the left, the mark, the name on the right. */}
            <div className="home-hero-notes">
              <p className="home-hero-note" data-intro="type" data-outro="type">
                Est. 2026
              </p>
            </div>
            <span className="home-hero-mark" aria-hidden="true" data-intro="fade" data-intro-shift="100%" data-outro="spin" />
            <p className="home-hero-tagline" data-intro="type" data-outro="type">
              Anisotropy
            </p>
          </div>
        </div>
        {/* Three seconds after the load-in the words are taken away and the clip plays alone (components/home/hero-outro.tsx). */}
        <HeroOutro />
        {/* Comes up at the foot of the clip once the words have left (ADR-0077 amendment 22). */}
        <ScrollToExplore />
        {/* UC San Diego's The Basement mark, in the bottom left corner of the hero's box (ADR-0081). It fades in with the
            load-in and out when the words leave (ADR-0070 amendment 4). */}
        <p className="home-hero-backed" data-intro="fade" data-outro="fade">
          <img src="/assets/partners/uc-san-diego-the-basement-white.png" alt="UC San Diego, The Basement" width={684} height={202} />
          {/* The programme the team is part of (ADR-0081), beside the mark of the place that runs it (ADR-0077 amendment 28). */}
          <span className="home-hero-cohort">Fall 2026 Launchpad cohort</span>
        </p>
      </section>
      {/* The laminate calculator and its tour left the home page on 2026-11-13 (ADR-0094): a feature, not the product. Their
          components are kept, unmounted (components/home/laminate-hero.tsx, demo-tour.tsx); the full calculator is still at
          /calculator and in the workspace. */}
      {/* The product demo (ADR-0094): the coupon workspace in four beats, in a white box the size of the clip, under it. */}
      <ProductDemo />
      {/* The sections under the demo are bands of the section kit (app/sections.css, ADR-0077 amendments 11, 14 and 16):
          Mission and Platform dark, About light, What is new dark. Each band opens with the kit's head. The four principles
          close the Mission band as a strip. */}
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
      <section className="band home-blurb home-platform" id="platform">
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
      {/* About keeps the old section's id, so links to #working still land. Each card is ready for a portrait and a profile
          link (lib/team.ts); until a person gives one, the frame holds their initials and the name is plain text. */}
      <section className="band is-light home-blurb home-about" id="working">
        <div className="band-head">
          <p className="band-label">03 / ABOUT</p>
          <div className="band-statement">
            <h2>Five people, two seats each.</h2>
            <p>
              One technical seat and one for the company per person. A lead decides alone inside the seat; anything that
              could alter results, cost, security, test plans or spending goes to the CEO. The repository is public, the
              decisions and their reasons with it.
            </p>
            <p className="home-about-cohort">Part of the Fall 2026 Launchpad cohort at The Basement, UC San Diego</p>
          </div>
        </div>
        <div className="home-faces">
          {team.map((person) => (
            <article className="home-face" key={person.name}>
              <div className="home-face-frame">
                {person.photo ? (
                  <>
                    <img src={person.photo} alt={`Portrait of ${person.name}`} width={800} height={1000} loading="lazy" decoding="async" />
                    {/* LinkedIn's mark comes up in the frame's corner under the pointer (ADR-0057 amendment 2). It is a link
                        once the person's profile address is in lib/team.ts; until then it is only drawn. */}
                    {person.linkedin ? (
                      <a
                        className="home-face-in"
                        href={person.linkedin}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`${person.name} on LinkedIn (opens in a new tab)`}
                      >
                        <LinkedInMark />
                      </a>
                    ) : (
                      <span className="home-face-in" aria-hidden="true">
                        <LinkedInMark />
                      </span>
                    )}
                  </>
                ) : (
                  <span aria-hidden="true">
                    {person.name
                      .split(" ")
                      .map((part) => part.charAt(0))
                      .join("")}
                  </span>
                )}
              </div>
              <h3>
                {person.linkedin ? (
                  <a
                    href={person.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`${person.name} on LinkedIn (opens in a new tab)`}
                  >
                    {person.name} <ArrowUpRight size={16} />
                  </a>
                ) : (
                  person.name
                )}
              </h3>
              <p>
                {person.role ? `${person.role}. ` : ""}
                {person.technical.charAt(0).toUpperCase() + person.technical.slice(1)}
                {person.company ? `; ${person.company}` : ""}.
              </p>
            </article>
          ))}
        </div>
        <Link className="home-link home-about-link" href="/about#team">
          The team on the About page <ArrowUpRight size={16} />
        </Link>
      </section>
      <section className="band home-blurb" id="news">
        <div className="band-head">
          <p className="band-label">04 / WHAT IS NEW</p>
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
