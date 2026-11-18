import test from "node:test";
import assert from "node:assert/strict";
import { CONTACT, MESSAGE_MAX, composeMail } from "../lib/contact-mail";
import { team } from "../lib/team";

// The contact page's one address and the email its form writes (ADR-0058 amendment 6).

test("the contact page writes to one person of the team, at one address", () => {
  assert.ok(team.some((person) => person.name === CONTACT.name), CONTACT.name);
  assert.match(CONTACT.email, /^[a-z0-9.]+@[a-z0-9.]+\.[a-z]+$/);
});

test("the form's email is addressed to the contact, says who writes, and carries the message and how to reply", () => {
  const mail = composeMail("someone@example.org", { name: "  Ada   Example ", company: "Example Works", email: " ada@example.com ", message: "First line.\r\nSecond & third?  " });
  const [to, query] = [mail.slice(0, mail.indexOf("?")), new URLSearchParams(mail.slice(mail.indexOf("?") + 1).replace(/\+/g, "%2B"))];
  assert.equal(to, "mailto:someone@example.org");
  assert.equal(query.get("subject"), "Inquiry from Ada Example, Example Works");
  assert.equal(query.get("body"), "First line.\r\nSecond & third?\r\n\r\nAda Example\r\nExample Works\r\nada@example.com");
  // Nothing in the address is left unescaped that would end it early or start another field.
  assert.ok(!/[ \n\r]/.test(mail) && mail.split("&").length === 2, mail);
});

test("without a company the email has no empty line for it, and a long message is cut at the form's limit", () => {
  const mail = composeMail("someone@example.org", { name: "Ada Example", email: "ada@example.com", message: "x".repeat(MESSAGE_MAX + 50) });
  const body = decodeURIComponent(mail.split("&body=")[1]);
  assert.equal(decodeURIComponent(mail.split("?subject=")[1].split("&")[0]), "Inquiry from Ada Example");
  assert.equal(body, `${"x".repeat(MESSAGE_MAX)}\r\n\r\nAda Example\r\nada@example.com`);
  // A name typed over several lines cannot add a line to the subject.
  assert.ok(!decodeURIComponent(composeMail("a@b.co", { name: "Ada\nBcc: x@y.z", email: "ada@example.com", message: "hi" }).split("?subject=")[1].split("&")[0]).includes("\n"));
});
