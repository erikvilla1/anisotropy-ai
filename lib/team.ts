/** The team as the shared brain records it (docs/brain/people.md), roles only: each person holds one technical seat and one
 * seat for the company. tests/team.test.ts keeps this list in step with that note. A name appears on the site only with
 * that person's consent (ADR-0057 amendment 1); removing a card is removing its line here. A photo or a profile link is
 * added only with that person's consent too (the same amendment); both are unset until then, and a card without a photo
 * shows the person's initials. */
export type Person = {
  name: string;
  /** The role named before the seats, when there is one. */
  role?: string;
  /** The technical seat, as people.md words it. */
  technical: string;
  /** The seat for the company, as people.md words it; the CEO's is the role itself. */
  company?: string;
  /** A portrait, as a path under public/ (for example "/assets/team/name.jpg"); the home page's card shows it in place of the initials. */
  photo?: string;
  /** The person's LinkedIn profile address; the name on the home page's card becomes a link to it. */
  linkedin?: string;
};

/** The cards' order is the lead's (2026-11-13): the two founders, then Tabassum in the middle, Jusung, and Kai at the right.
 * The portraits are cut from the originals by scripts/team-photos.py (ADR-0057 amendment 2). */
export const team: readonly Person[] = [
  { name: "Christopher Valerio", role: "Co-founder and CEO", technical: "prompt engineering and AI evaluation", photo: "/assets/team/christopher-valerio.jpg" },
  { name: "Erik Villa", role: "Co-founder", technical: "AI architecture and operations", company: "documentation and records", photo: "/assets/team/erik-villa.jpg" },
  { name: "Tabassum Zaman", technical: "fabrication, prototypes and mechanical testing", company: "partnerships and outreach", photo: "/assets/team/tabassum-zaman.jpg" },
  { name: "Jusung Park", technical: "reference modeling and validation", company: "operations and logistics", photo: "/assets/team/jusung-park.jpg" },
  { name: "Kai Saucedo", technical: "software and UI/UX", company: "marketing and communications", photo: "/assets/team/kai-saucedo.jpg" },
];
