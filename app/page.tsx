import { existsSync } from "node:fs";
import { join } from "node:path";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { ClosingBand } from "@/components/closing-band";
import { HeroHandover } from "@/components/home/hero-handover";
import { HeroOutro } from "@/components/home/hero-outro";
import { ProductDemo } from "@/components/home/product-demo";
import { ScrollToExplore } from "@/components/home/scroll-to-explore";
import { HeroVideoKeeper } from "@/components/home/hero-video-keeper";
import { serviceHref, services } from "@/lib/services";
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

/** What the feed shows: one card an item. It is empty for now, at the lead's word of 2026-11-14 ("this needs to be empty as
 * of right now; we have no published updates for the newsfeed", ADR-0077 amendment 41). An item added here gets a card. */
type NewsItem = { when: string; about: string; title: string; text: string };
const news: NewsItem[] = [];

/** The home page: the hero first (ADR-0076, ADR-0077), the product demo under it (ADR-0095), then bands on the mission, the
 * platform, the team and what is new, and the closing band. The workflow and the roadmap live on About. */
export default function Home() {
  return (
    <main id="main">
      {/* The hero and the demo share one wrapper, so the hero can stay in the window while the page scrolls to the demo's stage
          and dim away as the first beat comes up through it (ADR-0095 amendment 4, components/home/hero-handover.tsx). */}
      <div className="home-opening">
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
                Est 2026
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
      {/* The laminate calculator and its tour left the home page on 2026-11-13 (ADR-0095): a feature, not the product. Their
          components are kept, unmounted (components/home/laminate-hero.tsx, demo-tour.tsx); the full calculator is still at
          /calculator and in the workspace. */}
      {/* The product demo (ADR-0095 amendment 2): the coupon workspace in four beats, on black, a window tall, under the hero. */}
      <ProductDemo />
      <HeroHandover />
      </div>
      {/* The sections under the demo are bands of the section kit (app/sections.css, ADR-0077 amendments 11, 14 and 31), all
          on the light ground since amendment 33: after the demo's last beat the page is white. On this page a band's head is
          set as the demo's words are, in the middle (amendment 34, app/home.css). */}
      {/* Mission and Services are set side by side with a picture each (ADR-0077 amendment 37): Mission's words at the left
          and its picture at the right, Services the other way round. The picture is the hero's carbon weave for now, standing
          in for pictures still to come. Each picture goes where its band's own link goes, About and Services, and lifts
          under the pointer as a portrait does (amendment 39); the keyboard and a screen reader meet the worded link only,
          so the same place is not offered twice. */}
      <section className="band is-light home-blurb home-split home-mission" id="mission">
        <div className="band-head">
          <p className="band-label">Mission</p>
          <div className="band-statement">
            <h2>One record, from the layup to the test.</h2>
            <p>
              Composite structures are designed, analyzed, tested and built by different people with different tools, and the
              evidence gets lost between them. Anisotropy keeps those steps on one record, grounded in composite theory and
              real mechanical test data, so every answer comes with its assumptions and references.
            </p>
            <Link className="home-link" href="/about">
              Learn more about us <ArrowUpRight size={16} />
            </Link>
          </div>
        </div>
        <Link className="home-split-picture" href="/about" aria-hidden="true" tabIndex={-1} />
      </section>
      {/* The step to the services (ADR-0077 amendment 34): the five by name, each a link to its page, and the way to all of them. */}
      <section className="band is-light home-blurb home-split is-flipped home-platform" id="platform">
        <div className="band-head">
          <p className="band-label">Services</p>
          <div className="band-statement">
            <h2>Five ways to use it.</h2>
            <p>
              The same coupon record feeds every service. Two are built, two exist in part, one is stated as planned; each
              page says which.
            </p>
            <ul className="home-services" aria-label="Services">
              {services.map((service) => (
                <li key={service.slug}>
                  <Link href={serviceHref(service)}>{service.title}</Link>
                </li>
              ))}
            </ul>
            <Link className="home-link" href="/services">
              Explore the services <ArrowUpRight size={16} />
            </Link>
          </div>
        </div>
        <Link className="home-split-picture" href="/services" aria-hidden="true" tabIndex={-1} />
      </section>
      {/* About keeps the old section's id, so links to #working still land. Each card is ready for a portrait and a profile
          link (lib/team.ts); until a person gives one, the frame holds their initials and the name is plain text. The band's
          head stands on light grey from edge to edge and the portraits on white (ADR-0077 amendment 41, app/home.css). */}
      <section className="band is-light home-blurb home-about" id="working">
        <div className="band-head">
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
        {/* The band's label stands over the portraits, at their left edge, on the white (amendment 42). */}
        <p className="band-label home-faces-label">Team</p>
        <div className="home-faces">
          {team.map((person) => (
            <article className="home-face" key={person.name}>
              <div className="home-face-frame">
                {person.photo ? (
                  <>
                    <img src={person.photo} alt={`Portrait of ${person.name}`} width={800} height={1000} loading="lazy" decoding="async" />
                    {/* LinkedIn's mark comes up in the frame's corner under the pointer (ADR-0057 amendment 2). It is a link
                        once the person's profile address is in lib/team.ts; until then it is only drawn. The mark itself is
                        the picture the lead uploaded, drawn in black and white by app/home.css (ADR-0077 amendment 39). */}
                    {person.linkedin ? (
                      <a
                        className="home-face-in"
                        href={person.linkedin}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`${person.name} on LinkedIn (opens in a new tab)`}
                      />
                    ) : (
                      <span className="home-face-in" aria-hidden="true" />
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
                    {person.name}
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
      </section>
      <section className="band is-light home-blurb home-feed" id="news">
        <div className="band-head">
          <p className="band-label">What is new</p>
          <div className="band-statement">
            <h2>Lately.</h2>
            <p>{news.length ? "News from the team, as it happens." : "Nothing posted yet. News from the team will appear here."}</p>
          </div>
        </div>
        {news.length ? (
          <div className="home-news">
            {news.map((item) => (
              <article key={item.title}>
                <p className="home-news-meta">
                  <time>{item.when}</time>
                  <span>{item.about}</span>
                </p>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        ) : null}
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
