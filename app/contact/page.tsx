import Link from "next/link";
import { ArrowUpRight, Mail } from "lucide-react";
import "../inner-pages.css";
import "../services/services.css";

export const metadata = {
  title: "Contact — Anisotropy",
  description: "Write to Anisotropy about a composite coupon, a material or a question about the platform.",
};

/** The contact page (audit of 2026-10-31, item 15): one address for now, a co-founder's; an anisotropy.dev address follows.
 * The site is a static export, so there is no form; the address is a plain mailto link. */
export default function Contact() {
  return (
    <main id="main" className="kit-page contact-page">
      <section className="page-opening">
        <p className="page-opening-label">CONTACT / WRITE TO US</p>
        <h1 className="page-opening-title">
          Tell us about
          <br />
          <em>your coupon.</em>
        </h1>
        <div className="page-opening-grid">
          <div className="page-opening-copy">
            <p>
              A material you need to understand, a test you are planning, a result you want checked, or a question
              about what the platform does. One address reaches the team.
            </p>
          </div>
          <div className="page-opening-note">
            <p className="page-opening-note-label">ONE ADDRESS, FOR NOW</p>
            <p>
              Erik Villa, co-founder.
              <br />
              An anisotropy.dev address will follow.
            </p>
          </div>
        </div>
      </section>
      <section className="band is-light contact-band">
        <div className="band-head contact-row">
          <p className="band-label">EMAIL</p>
          <div className="band-statement">
            <a className="contact-email" href="mailto:erikvilla947@gmail.com">
              <Mail size={28} strokeWidth={1.4} /> erikvilla947@gmail.com
            </a>
            <p>
              What helps us answer quickly: the material and where its data comes from, the test (tension, open hole,
              bending, a plate), the dimensions and the layup, and what you need back.
            </p>
          </div>
        </div>
        <div className="band-head contact-row">
          <p className="band-label">BEFORE YOU WRITE</p>
          <div className="band-statement contact-links">
            <Link className="kit-link" href="/services/finite-element-modeling#access">
              Access to the studio <ArrowUpRight size={18} />
            </Link>
            <Link className="kit-link" href="/library">
              The materials library <ArrowUpRight size={18} />
            </Link>
            <a className="kit-link" href="https://github.com/erikvilla1/anisotropy-ai" target="_blank" rel="noreferrer">
              The repository on GitHub <ArrowUpRight size={18} />
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
