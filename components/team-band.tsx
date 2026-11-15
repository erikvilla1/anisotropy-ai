import { team } from "@/lib/team";
import "./team-band.css";

/** The team band: who the team is, the programme it is part of, and the five portraits (lib/team.ts). It is on the About
 * page, as its last section, under the id links to the team use; until ADR-0077 amendment 73 it stood on the home page.
 * Each card is ready for a portrait and a profile link; until a person gives one, the frame holds their initials and the
 * name is plain text. The band is one light grey block, its head close over the portraits (amendments 59 and 61); its
 * rules are components/team-band.css. */
export function TeamBand() {
  return (
    <section className="band is-light team-band" id="team">
      {/* The head spans the page as the portraits do (ADR-0077 amendment 61): the band's label and its heading at the left,
          and from the halfway line who the team is and the programme it is part of. The degrees are said of the team as a
          whole, as the lead gave them on 2026-11-14, and of no one by name. The Basement's mark stands beside the cohort
          since ADR-0081 amendment 3. How the team decides is not said here. */}
      <div className="band-head team-band-head">
        <div className="team-band-title">
          <p className="band-label">Team</p>
          <h2>From university to industry.</h2>
        </div>
        <div className="team-band-text">
          <p>
            Five engineers trained in structures and mechanics: two are pursuing PhDs in structural engineering, two hold a
            BS in structural engineering and one a BS in mechanical engineering. Between them they cover modeling and
            validation, fabrication and mechanical testing, and the software and AI that connect them.
          </p>
          {/* The Basement's mark, drawn in black, beside the cohort (ADR-0081 amendment 3, which records the lead's word
              that The Basement agreed to its use). The picture says the programme's name, so the words do not repeat it. */}
          <div className="team-band-cohort">
            <img className="team-band-mark" src="/assets/partners/uc-san-diego-the-basement.png" alt="UC San Diego, The Basement" width={684} height={202} loading="lazy" decoding="async" />
            <span>Part of the Fall 2026 Launchpad cohort</span>
          </div>
        </div>
      </div>
      <div className="team-faces">
        {team.map((person) => (
          <article className="team-face" key={person.name}>
            <div className="team-face-frame">
              {person.photo ? (
                <>
                  <img src={person.photo} alt={`Portrait of ${person.name}`} width={800} height={1000} loading="lazy" decoding="async" />
                  {/* LinkedIn's mark comes up in the frame's corner under the pointer (ADR-0077 amendment 29). It is a link
                      once the person's profile address is in lib/team.ts; until then it is only drawn. The mark itself is
                      the picture the lead uploaded, drawn in black and white by components/team-band.css (ADR-0077 amendment 39). */}
                  {person.linkedin ? (
                    <a
                      className="team-face-in"
                      href={person.linkedin}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`${person.name} on LinkedIn (opens in a new tab)`}
                    />
                  ) : (
                    <span className="team-face-in" aria-hidden="true" />
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
            {/* One short line, as a company's page names its officers (amendment 43). */}
            <p>{person.title}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
