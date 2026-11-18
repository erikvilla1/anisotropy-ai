/** The contact page's one address and the email its form writes (ADR-0058 amendment 6). The site is a static export with
 * nothing behind it to receive a form, so the form sends nothing: it writes an email to the address below and hands it to the
 * visitor's own email app, which sends it. */

/** Who the contact page writes to: one person, so a visitor does not have to choose (the lead, 2026-11-14). The name is the
 * one lib/team.ts gives; the address is the one the founder gave for the page on 2026-11-12. */
export const CONTACT = { name: "Christopher Valerio", email: "chvalerio@ucsd.edu" } as const;

/** The longest message the form takes: an address that carries a whole email must stay short enough for every email app. */
export const MESSAGE_MAX = 1500;

export type ContactFields = { name: string; company?: string; email: string; message: string };

/** One line of what a visitor typed: no line breaks, no space at its ends. */
const line = (value: string | undefined): string => (value ?? "").replace(/\s+/g, " ").trim();

/** The email the form writes, as the address an email app opens: the subject says who writes, and the body is the message as
 * typed, then the visitor's name, company and address on lines of their own, so a reply can reach them. Line ends are
 * written as email expects them. */
export function composeMail(to: string, fields: ContactFields): string {
  const name = line(fields.name), company = line(fields.company), email = line(fields.email);
  const message = (fields.message ?? "").replace(/\r\n?/g, "\n").trim().slice(0, MESSAGE_MAX);
  const subject = `Inquiry from ${name}${company ? `, ${company}` : ""}`;
  const body = [message, "", name, company, email].filter((part, index) => index < 2 || part).join("\n").replace(/\n/g, "\r\n");
  return `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
