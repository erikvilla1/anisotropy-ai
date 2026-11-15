import { existsSync } from "node:fs";
import { join } from "node:path";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { ClosingBand } from "@/components/closing-band";
import { HeroHandover } from "@/components/home/hero-handover";
import { HeroOutro } from "@/components/home/hero-outro";
import { ProductDemo } from "@/components/home/product-demo";
import { ScrollToExplore } from "@/components/home/scroll-to-explore";
import { SplitPicture } from "@/components/home/split-picture";
import { HeroVideoKeeper } from "@/components/home/hero-video-keeper";
import { releaseDay, releases } from "@/lib/changelog";
import { serviceHref, services } from "@/lib/services";
import { team } from "@/lib/team";
import "./home.css";

/** The hero clip's web copy (ADR-0069), written by scripts/hero-video.sh into public/media, where it and its poster are committed
 * since ADR-0069 amendment 1. A build without it shows the still photo instead. */
const heroVideo = existsSync(join(process.cwd(), "public", "media", "hero.mp4"));
// Plain HTML so the browser sees "muted" before React runs, which autoplay requires. Only a window 768 px wide or more, whose
// visitor has not asked for reduced motion, gets the source, so phones and those visitors keep the poster frame and download no
// clip; the page loads the clip's first frame and length at most until it plays.
const heroVideoHtml =
  '<video autoplay muted loop playsinline preload="metadata" poster="/media/hero.jpg" disablepictureinpicture tabindex="-1">' +
  '<source src="/media/hero.mp4" type="video/mp4" media="(min-width: 768px) and (prefers-reduced-motion: no-preference)"></video>';

/** The home page: the hero first (ADR-0076, ADR-0077), the product demo under it (ADR-0095), then bands on the mission, the
 * platform, the team and the changelog, and the closing band. The workflow and the roadmap live on About. */
export default function Home() {
  return (
    <main id="main">
      {/* The hero and the demo share one wrapper, so the hero can stay in the window while the page scrolls to the demo's stage
          and dim away as the first beat comes up through it (ADR-0095 amendment 4, components/home/hero-handover.tsx). */}
      <div className="home-opening">
      <section className="home-hero" id="overview" aria-labelledby="home-hero-title">
        <div className={heroVideo ? "home-hero-media has-video" : "home-hero-media"} aria-hidden="true">
          {heroVideo ? <div className="home-hero-video" dangerouslySetInnerHTML={{ __html: heroVideoHtml }} /> : null}
        </div>
        {/* The lens (ADR-0071) is hidden for now at the lead's request (amendment 1); `<HeroLens />` from components/home/hero-lens.tsx brings it back. */}
        {/* The words (ADR-0077 amendments 19, 27, 47 and 51): one statement, written as a sentence, in the clip's lower left,
            and over it a line of the mark, the name, a hairline and the year. The load-in (ADR-0070 amendments 1 and 4) types
            the statement and the small lines in, and a text cursor blinks at the statement's end (components/intro-text.ts). */}
        <div className="home-hero-stack">
          <h1 className="home-hero-title" id="home-hero-title" data-intro="type" data-outro="type" data-intro-caret="">
            One engineering platform
            <br />
            for composite theory
            <br />
            and real test data
            <span className="type-caret" aria-hidden="true" />
          </h1>
          <div className="home-hero-row">
            {/* The line of ADR-0077 amendments 28 and 47: in the page's order the year, the mark, the hairline, the name; the
                stylesheet shows the mark first and the year last. */}
            <div className="home-hero-notes">
              <p className="home-hero-note" data-intro="type" data-outro="type">
                Est 2026
              </p>
            </div>
            <span className="home-hero-mark" aria-hidden="true" data-intro="fade" data-intro-shift="100%" data-outro="spin" />
            {/* The hairline between the name and the year (ADR-0077 amendment 52): it fades in with the load-in and goes as
                the lines begin to go, so nothing of the line is left on the clip. */}
            <span className="home-hero-rule" aria-hidden="true" data-intro="fade" data-intro-shift="0px" data-outro="fade" data-outro-at="start" />
            <p className="home-hero-tagline" data-intro="type" data-outro="type">
              Anisotropy
            </p>
          </div>
        </div>
        {/* Three seconds after the load-in the words are taken away and the clip plays alone (components/home/hero-outro.tsx). */}
        <HeroOutro />
        {/* Comes up at the foot of the clip once the words have left (ADR-0077 amendment 22). */}
        <ScrollToExplore />
        {/* The pause button of the clip, in its top right corner (ADR-0077 amendment 50); it keeps the clip playing until pressed. */}
        {heroVideo ? <HeroVideoKeeper /> : null}
        {/* Where the cohort meets, in the bottom left corner of the hero's box: in words, until written permission to show The
            Basement's mark is recorded (ADR-0081 amendment 2), with the cohort beside it (ADR-0077 amendment 28). It fades in
            with the load-in and out when the words leave (ADR-0070 amendment 4). */}
        <p className="home-hero-backed" data-intro="fade" data-outro="fade">
          The Basement, UC San Diego{" "}
          {/* The programme the team is part of (ADR-0081), beside the place that runs it (ADR-0077 amendment 28). */}
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
          in for pictures still to come. A picture is a picture and no longer a link (amendment 53, which ended amendment
          39's): the band's worded link is the one way to its page. Under a mouse's pointer, a crosshair over the picture,
          a small lens shows the photograph in the demo's colours (amendment 48, components/home/split-picture.tsx); the
          filter it draws through is the one below. */}
      <svg className="home-fea-filter" width="0" height="0" aria-hidden="true" focusable="false">
        <filter id="home-fea" colorInterpolationFilters="sRGB">
          {/* The photograph's light and dark alone, smoothed and stretched over the whole range, */}
          <feColorMatrix type="matrix" values="0.2126 0.7152 0.0722 0 0  0.2126 0.7152 0.0722 0 0  0.2126 0.7152 0.0722 0 0  0 0 0 1 0" />
          <feGaussianBlur stdDeviation="6" />
          <feComponentTransfer>
            <feFuncR type="linear" slope="2.9" intercept="-0.42" />
            <feFuncG type="linear" slope="2.9" intercept="-0.42" />
            <feFuncB type="linear" slope="2.9" intercept="-0.42" />
          </feComponentTransfer>
          {/* then through the demo's scale (lib/demo-wing.ts, RAINBOW): blue, cyan, green, yellow, red. */}
          <feComponentTransfer>
            <feFuncR type="table" tableValues="0 0 0 1 1" />
            <feFuncG type="table" tableValues="0 1 1 1 0" />
            <feFuncB type="table" tableValues="1 1 0 0 0" />
          </feComponentTransfer>
        </filter>
      </svg>
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
              Learn more about us <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </div>
        <SplitPicture />
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
              Explore the services <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </div>
        <SplitPicture />
      </section>
      {/* The team keeps the old section's id, so links to #working still land. Each card is ready for a portrait and a profile
          link (lib/team.ts); until a person gives one, the frame holds their initials and the name is plain text. The band is
          one light grey block, its head close over the portraits (ADR-0077 amendment 59, app/home.css). */}
      <section className="band is-light home-blurb home-about" id="working">
        <div className="band-head">
          <div className="band-statement">
            {/* Who is behind the product and what they cover, for a visitor (ADR-0077 amendment 55): the fields are the
                technical seats docs/brain/people.md records, in a visitor's words. How the team decides is not said here. */}
            <h2>The team behind the platform.</h2>
            <p>
              Five people covering modeling and validation, fabrication and mechanical testing, and the software and AI that
              connect them.
            </p>
          </div>
        </div>
        {/* The band's label stands over the portraits, at their left edge (amendment 42). */}
        <p className="band-label home-faces-label">Team</p>
        <div className="home-faces">
          {team.map((person) => (
            <article className="home-face" key={person.name}>
              <div className="home-face-frame">
                {person.photo ? (
                  <>
                    <img src={person.photo} alt={`Portrait of ${person.name}`} width={800} height={1000} loading="lazy" decoding="async" />
                    {/* LinkedIn's mark comes up in the frame's corner under the pointer (ADR-0077 amendment 29). It is a link
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
              {/* One short line, as a company's page names its officers (amendment 43); the two seats in full are on About. */}
              <p>{person.title}</p>
            </article>
          ))}
        </div>
      </section>
      {/* The changelog (ADR-0077 amendment 46): where the versions the team publishes are listed, each with its day, its
          name and what changed in it, line by line and tagged by kind. The list is lib/changelog.ts; it is empty until a
          version is published, and the band then says so. */}
      <section className="band is-light home-blurb home-feed" id="changelog">
        {/* The band is white (amendment 59), and its words stand on a card in the colours the demo gives its analysis, blurred into one
            another (amendment 49), with a thin grid over the colours that fades out half way up the card (amendment 54). */}
        <div className="home-feed-card">
        <div className="band-head">
          <p className="band-label">Changelog</p>
          <div className="band-statement">
            <h2>Every release, and what changed.</h2>
            <p>{releases.length ? "Each published version, newest first." : "No releases published yet. Each version and what changed in it will be listed here."}</p>
          </div>
        </div>
        {releases.length ? (
          <ol className="home-changelog">
            {releases.map((release) => (
              <li key={release.version}>
                <div className="home-changelog-when">
                  <time dateTime={release.date}>{releaseDay(release.date)}</time>
                  <span className="home-changelog-version">{release.version}</span>
                </div>
                <div className="home-changelog-what">
                  <h3>{release.title}</h3>
                  {/* A kind and the change under it: a definition list. The kind's column is fixed, so every change
                      starts on one line down the list. */}
                  <dl>
                    {release.changes.map((change) => (
                      <div key={change.text}>
                        <dt>
                          <span className="home-changelog-kind" data-kind={change.kind}>
                            {change.kind}
                          </span>
                        </dt>
                        <dd>{change.text}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </li>
            ))}
          </ol>
        ) : null}
        </div>
      </section>
      {/* The home page's closing band is dark grey, between the changelog's light band and the black footer (amendment 54). */}
      <ClosingBand
        dark
        label="THE NEXT LAYER STARTS WITH A QUESTION."
        heading={["Let’s define what", "comes next."]}
        action={{ label: "Contact us", href: "/contact" }}
        links={{
          label: "EXPLORE THE RESEARCH",
          items: [{ label: "Materials library", href: "/library" }],
        }}
      />
    </main>
  );
}
