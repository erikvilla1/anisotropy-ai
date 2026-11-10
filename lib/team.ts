/** The team as the shared brain records it (docs/brain/people.md), roles only: each person holds one technical seat and one
 * seat for the company. tests/team.test.ts keeps this list in step with that note. A name appears on the site only with
 * that person's consent (ADR-0057 amendment 1); removing a card is removing its line here. */
export type Person = {
  name: string;
  /** The role named before the seats, when there is one. */
  role?: string;
  /** The technical seat, as people.md words it. */
  technical: string;
  /** The seat for the company, as people.md words it; the CEO's is the role itself. */
  company?: string;
};

export const team: readonly Person[] = [
  { name: "Christopher Valerio", role: "Co-founder and CEO", technical: "prompt engineering and AI evaluation" },
  { name: "Erik Villa", role: "Co-founder", technical: "AI architecture and operations", company: "documentation and records" },
  { name: "Kai Saucedo", technical: "software and UI/UX", company: "marketing and communications" },
  { name: "Jusung Park", technical: "reference modeling and validation", company: "operations and logistics" },
  { name: "Tabassum Zaman", technical: "fabrication, prototypes and mechanical testing", company: "partnerships and outreach" },
];
