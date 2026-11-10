import Link from "next/link";
import { ArrowUpRight, Mail } from "lucide-react";
import "../services/services.css";

export const metadata = {
  title: "Contact — Anisotropy",
  description: "Write to Anisotropy about a composite coupon, a material or a question about the platform.",
};

/** The contact page (audit of 2026-10-31, item 15): one address for now, a co-founder's; an anisotropy.dev address follows.
 * The site is a static export, so there is no form; the address is a plain mailto link. */
export default function Contact() {
  return (
    <main id="main" className="inner-page contact-page">
      <section className="section page-intro">
        <span className="eyebrow">CONTACT / WRITE TO US</span>
        <div className="intro-grid">
          <div>
            <h1>
              Tell us about
              <br />
              <em>your coupon.</em>
            </h1>
            <p>
              A material you need to understand, a test you are planning, a result you want checked, or a question
              about what the platform does. One address reaches the team.
            </p>
          </div>
          <div className="intro-aside">
            <span className="status-dot" />
            <span>ONE ADDRESS, FOR NOW</span>
            <p>
              Erik Villa, co-founder.
              <br />
              An anisotropy.dev address will follow.
            </p>
          </div>
        </div>
      </section>
      <section className="section contact-section">
        <div className="contact-card">
          <span className="tiny-label">EMAIL</span>
          <a className="contact-email" href="mailto:erikvilla947@gmail.com">
            <Mail size={22} strokeWidth={1.4} /> erikvilla947@gmail.com
          </a>
          <p>
            What helps us answer quickly: the material and where its data comes from, the test (tension, open hole,
            bending, a plate), the dimensions and the layup, and what you need back.
          </p>
        </div>
        <div className="contact-links">
          <span className="tiny-label">BEFORE YOU WRITE</span>
          <Link href="/services/finite-element-modeling#access">
            Access to the studio <ArrowUpRight size={15} />
          </Link>
          <Link href="/library">
            The materials library <ArrowUpRight size={15} />
          </Link>
          <a href="https://github.com/erikvilla1/anisotropy-ai" target="_blank" rel="noreferrer">
            The repository on GitHub <ArrowUpRight size={15} />
          </a>
        </div>
      </section>
    </main>
  );
}
