import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
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
    // The photo and the profile link are addresses, not words about the person; the test below checks them.
    for (const value of [person.name, person.title, person.role, person.technical, person.company])
      assert.ok(!/@|\+?\d{3}[\s-]?\d{3}/.test(String(value ?? "")), `${person.name}: a contact detail`);
    assert.deepEqual(Object.keys(person).filter((key) => !["name", "title", "role", "technical", "company", "photo", "linkedin"].includes(key)), []);
    // The card's one line is a title of a few words, the lead's (ADR-0077 amendment 45): short, and a title only.
    assert.ok(person.title.trim().length > 0 && person.title.length <= 34, `${person.name}: the one line "${person.title}"`);
    assert.ok(!/[.!?]/.test(person.title), `${person.name}: the one line is a title, not a sentence`);
  }
  assert.equal(new Set(team.map((person) => person.name)).size, team.length);
});

// A portrait and a profile link are optional and added only with the person's consent (ADR-0057 amendment 1). When one is
// set, the home page's card uses it, so it has to be a file the site serves or an address of the one kind the card links to.
test("a photo is a file under public/ and a profile link is a LinkedIn profile address", () => {
  for (const person of team) {
    if (person.photo !== undefined) {
      assert.match(person.photo, /^\/[\w./-]+\.(jpg|jpeg|png|webp|avif)$/, `${person.name}: photo "${person.photo}"`);
      assert.ok(existsSync(join(process.cwd(), "public", person.photo)), `${person.name}: public${person.photo} does not exist`);
    }
    if (person.linkedin !== undefined)
      assert.match(person.linkedin, /^https:\/\/(www\.)?linkedin\.com\/in\/[\w%-]+\/?$/, `${person.name}: profile link "${person.linkedin}"`);
  }
});
