import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { team } from "../lib/team";

// The team section of the About page repeats the shared brain's people note, roles only (ADR-0057). If the note changes,
// this test says which line of lib/team.ts no longer matches it.

const people = readFileSync(join(process.cwd(), "docs", "brain", "people.md"), "utf8").toLowerCase();

test("every name and seat on the site is in docs/brain/people.md, and nothing beyond a role is stated", () => {
  assert.equal(team.length, 5);
  for (const person of team) {
    assert.ok(people.includes(`### ${person.name.toLowerCase()}`), `${person.name} is not a heading of people.md`);
    assert.ok(people.includes(person.technical.toLowerCase()), `${person.name}: technical seat "${person.technical}"`);
    if (person.company) assert.ok(people.includes(person.company.toLowerCase()), `${person.name}: company seat "${person.company}"`);
    if (person.role) assert.ok(people.includes(person.role.toLowerCase()), `${person.name}: role "${person.role}"`);
    for (const value of Object.values(person)) assert.ok(!/@|\+?\d{3}[\s-]?\d{3}/.test(String(value)), `${person.name}: a contact detail`);
  }
  assert.equal(new Set(team.map((person) => person.name)).size, team.length);
});
