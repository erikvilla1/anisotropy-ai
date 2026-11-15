import { Mail } from "lucide-react";
import { ContactForm } from "@/components/contact/contact-form";
import { ContactGlobe } from "@/components/contact/contact-globe";
import { CONTACT } from "@/lib/contact-mail";
import { team } from "@/lib/team";
import "../inner-pages.css";
import "./contact.css";

export const metadata = {
  title: "Contact",
  description: "Write to Anisotropy about a composite coupon, a material or a question about the platform.",
};

/** The seat the contact is named by: the role when the person has one, else the seat for the company. */
function seatOf(name: string): string {
  const person = team.find((member) => member.name === name);
  const seat = person?.role ?? person?.company ?? "";
  return seat.charAt(0).toLowerCase() + seat.slice(1);
}

/** The contact page (ADR-0058 amendments 5 to 7): a white page under the header's bar, two columns that fit a laptop's
 * window without scrolling. At the left, how to reach us: a small label, the page's heading, what to write about, one
 * address (lib/contact-mail.ts), plain text inside a mailto link so it can be copied as well as clicked, over the upper half
 * of a slowly turning wireframe globe (components/contact/contact-globe.tsx). At the right, a card with a form that writes
 * the email for the visitor (components/contact/contact-form.tsx). The large statement that opened the page is gone
 * (amendment 7): it pushed the form below the window. The site is a static export, so nothing is sent from the page: the
 * visitor's own email app sends. */
export default function Contact() {
  return (
    <main id="main" className="kit-page contact-page">
      <section className="page-opening contact-opening">
        <div className="contact-columns">
          <div className="contact-reach">
            <p className="contact-label">CONTACT</p>
            <h1>Get in touch</h1>
            <p>
              A material you need to understand, a test you are planning, a result you want checked, or a question about
              what the platform does. ASTM D3039 unnotched tension is offered today.
            </p>
            <div className="contact-address">
              <span className="contact-person">
                {CONTACT.name}, {seatOf(CONTACT.name)}
              </span>
              <a className="contact-email" href={`mailto:${CONTACT.email}`}>
                <span className="contact-email-icon">
                  <Mail size={18} strokeWidth={1.5} aria-hidden="true" />
                </span>
                {CONTACT.email}
              </a>
            </div>
            <div className="contact-globe-window">
              <ContactGlobe />
            </div>
          </div>
          <div className="contact-card">
            <div className="contact-card-head">
              <h2>Send a message</h2>
              <p>Fill this in and we will write back to the address you give.</p>
            </div>
            <div className="contact-card-rule" aria-hidden="true" />
            <ContactForm to={CONTACT.email} />
          </div>
        </div>
      </section>
    </main>
  );
}
