"use client";

import { useState, type FormEvent } from "react";
import { ArrowRight } from "lucide-react";
import { MESSAGE_MAX, composeMail } from "@/lib/contact-mail";

/** The contact page's form (ADR-0058 amendment 6). It sends nothing: the site has nothing behind it to receive a form. A press
 * on its button writes an email to `to` from what was typed (lib/contact-mail.ts) and opens the visitor's email app with it,
 * and the visitor sends it from there. The line under the button says so before the press, and after it gives the same email
 * as a link, for a browser that opened nothing. */
export function ContactForm({ to }: { to: string }) {
  const [written, setWritten] = useState<string | null>(null);
  function write(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const typed = new FormData(event.currentTarget);
    const field = (name: string) => String(typed.get(name) ?? "");
    const mail = composeMail(to, { name: field("name"), company: field("company"), email: field("email"), message: field("message") });
    setWritten(mail);
    window.location.href = mail;
  }
  return (
    <form className="contact-form" onSubmit={write}>
      <div className="contact-form-pair">
        <label className="contact-field">
          <span>Full name</span>
          <input name="name" type="text" autoComplete="name" required maxLength={120} />
        </label>
        <label className="contact-field">
          <span>
            Company <i>optional</i>
          </span>
          <input name="company" type="text" autoComplete="organization" maxLength={120} />
        </label>
      </div>
      <label className="contact-field">
        <span>Email address</span>
        <input name="email" type="email" autoComplete="email" required maxLength={200} />
      </label>
      {/* The help under the message is not part of its label: it is the field's description. */}
      <div className="contact-field">
        <label htmlFor="contact-message">Message</label>
        <textarea id="contact-message" name="message" rows={5} required maxLength={MESSAGE_MAX} aria-describedby="contact-message-help" />
        <small id="contact-message-help">The material and its data source, the test, the dimensions and layup, and what you need back.</small>
      </div>
      <button type="submit" className="contact-submit">
        Open in your email app <ArrowRight size={16} aria-hidden="true" />
      </button>
      <p className="contact-form-note" role="status">
        {written ? (
          <>
            Your email app should have opened with the message written. If it did not, <a href={written}>open the email here</a>, or write to {to}.
          </>
        ) : (
          "Nothing is sent from this page. Your email app opens with the message written, and you send it from there."
        )}
      </p>
    </form>
  );
}
