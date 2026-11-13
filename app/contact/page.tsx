import Link from "next/link";
import { ArrowRight, Mail } from "lucide-react";
import { team } from "@/lib/team";
import "../inner-pages.css";
import "../services/services.css";

export const metadata = {
  title: "Contact",
  description: "Write to Anisotropy about a composite coupon, a material or a question about the platform.",
};

/** Who answers which question. The addresses are the ones Erik gave on 2026-11-12 (the audit of 2026-11-12, decision D2); each
 * person's name and seat are the ones lib/team.ts gives them, and nothing else about them is shown. */
const contacts: { topic: string; people: { name: string; email: string }[] }[] = [
  {
    topic: "General and engineering inquiries",
    people: [
      { name: "Erik Villa", email: "e1villa@ucsd.edu" },
      { name: "Christopher Valerio", email: "chvalerio@ucsd.edu" },
    ],
  },
  {
    topic: "Marketing inquiries",
    people: [{ name: "Kai Saucedo", email: "ka1saucedo@outlook.com" }],
  },
];

/** The seat a contact is named by: the role when the person has one, else the seat for the company. */
function seatOf(name: string): string {
  const person = team.find((member) => member.name === name);
  const seat = person?.role ?? person?.company ?? "";
  return seat.charAt(0).toLowerCase() + seat.slice(1);
}

/** The contact page (audit of 2026-10-31, item 15; ADR-0058 amendment 4). The site is a static export, so there is no form; each
 * address is plain text inside a mailto link, so it can be copied as well as clicked. */
export default function Contact() {
  return (
    <main id="main" className="kit-page contact-page">
      <section className="page-opening">
        <p className="page-opening-label">CONTACT / WRITE TO US</p>
        <h1 className="page-opening-title">
          Tell us about{" "}
          <br />
          <em>your coupon.</em>
        </h1>
        <div className="page-opening-grid">
          <div className="page-opening-copy">
            <p>
              A material you need to understand, a test you are planning, a result you want checked, or a question
              about what the platform does. Write to the address for your question below.
            </p>
          </div>
          <div className="page-opening-note">
            <p className="page-opening-note-label">WHO ANSWERS</p>
            <p>
              General and engineering: the co-founders.
              <br />
              Marketing: Kai Saucedo.
            </p>
          </div>
        </div>
      </section>
      <section className="band is-light contact-band">
        <div className="band-head contact-row">
          <h2 className="band-label">EMAIL</h2>
          <div className="band-statement contact-groups">
            {contacts.map((group) => (
              <div className="contact-group" key={group.topic}>
                <h3 className="kit-mono">{group.topic}</h3>
                <ul>
                  {group.people.map((person) => (
                    <li key={person.email}>
                      <span className="contact-person">
                        {person.name}, {seatOf(person.name)}
                      </span>
                      <a className="contact-email" href={`mailto:${person.email}`}>
                        <Mail size={22} strokeWidth={1.4} aria-hidden="true" />
                        {person.email}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            <p>
              Include the material and its data source, the test, the dimensions and layup, and what you need back.
              ASTM D3039 unnotched tension is offered today.
            </p>
          </div>
        </div>
        <div className="band-head contact-row">
          <h2 className="band-label">BEFORE YOU WRITE</h2>
          <div className="band-statement contact-links">
            <Link className="kit-link" href="/services/finite-element-modeling#access">
              Workspace access <ArrowRight size={18} aria-hidden="true" />
            </Link>
            <Link className="kit-link" href="/library">
              The materials library <ArrowRight size={18} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
