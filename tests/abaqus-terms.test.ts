import assert from "node:assert/strict";
import test from "node:test";
import { ABAQUS_TERMS, isConditionOrLoad, setupAsked, termAsked, termLines, termNamed } from "../lib/abaqus-terms";
import { asksWhy } from "../lib/result-why";
import { bannedIn } from "../lib/studio-copy";

test("each Abaqus term is said in one short sentence of meaning and one of what Anisotropy does, and no name belongs to two terms (ADR-0110)", () => {
  const seen = new Map<string, string>();
  for (const term of ABAQUS_TERMS) {
    assert.ok(term.names.length, term.id);
    for (const sentence of [term.means, ...Object.values(term.exact ?? {})]) {
      assert.match(sentence, /^[A-Z].*\.$/, `${term.id}: ${sentence}`);
      assert.ok(sentence.split(/\s+/).length <= 32, `${term.id} is too long: ${sentence}`);
    }
    assert.ok(term.here.split(/\s+/).length <= 45, `${term.id}: ${term.here}`);
    for (const name of term.names) {
      assert.equal(name, name.toLowerCase(), name);
      assert.equal(seen.get(name), undefined, `${name} is a name of ${seen.get(name)} and ${term.id}`);
      seen.set(name, term.id);
    }
    for (const name of Object.keys(term.exact ?? {})) assert.ok(term.names.includes(name), `${term.id}: ${name}`);
  }
  // our own words: no sentence is lifted from a manual's procedure ("Toggle on", "click", "dialog box", "module")
  const all = ABAQUS_TERMS.flatMap((t) => [t.means, t.here]).join(" ");
  assert.doesNotMatch(all, /toggle|dialog|click mouse|module|model tree|abaqus\/cae/i);
  // and in the product's own words: no program is named (ADR-0091), so the answers can be shown as they are
  for (const sentence of ABAQUS_TERMS.flatMap((t) => [t.title, t.means, t.here, ...Object.values(t.exact ?? {})])) assert.deepEqual(bannedIn(sentence), [], sentence);
});

test("a question of what a word means is answered from the glossary; a question of a value or of why is left alone (ADR-0110)", () => {
  const asked = (text: string) => termAsked(text)?.term.id ?? null;
  assert.equal(asked("what is a boundary condition?"), "boundary-condition");
  assert.equal(asked("What's a BC"), "boundary-condition");
  assert.equal(asked("what are BCs?"), "boundary-condition");
  assert.equal(asked("what does encastre mean?"), "encastre");
  assert.equal(asked("Encastre?"), "encastre");
  assert.equal(asked("what is a partition"), "partition");
  assert.equal(asked("define section point"), "section-point");
  assert.equal(asked("what does XSYMM mean in Abaqus?"), "symmetry");
  assert.equal(asked("what is a seed?"), "seed");
  assert.equal(asked("what is meant by a step"), "step");
  // a value, a place or a reason: the lookup's and the why answers' own
  for (const text of ["what is the stress at element 12?", "what is the reaction force?", "what does the failure index mean?", "why is ply 4 in compression?",
    "what is the step size", "show load", "make it compression", "10 kN", "stress here"]) {
    assert.equal(asked(text), null, text);
  }
  // the glossary is read before the why answers, so a word's meaning never goes to a model
  assert.equal(asksWhy("what does encastre mean?"), true);
});

test("a question of this model's own boundary conditions or loads is told from a question of the word (ADR-0110)", () => {
  assert.deepEqual(termAsked("what are the boundary conditions?"), { term: termNamed("bc"), name: "boundary conditions", ofModel: true });
  assert.equal(termAsked("what is the load here?")?.ofModel, true);
  assert.equal(termAsked("show the BCs")?.ofModel, true);
  assert.equal(termAsked("explain the loads applied")?.ofModel, true);
  assert.equal(termAsked("what is a load?")?.ofModel, false);
});

test("a name with one exact meaning is answered with it: U2, ZSYMM, CF3, RF2 (ADR-0110)", () => {
  const lines = (text: string) => { const q = termAsked(text); assert.ok(q, text); return termLines(q); };
  assert.deepEqual([lines("what is U2?").title, lines("what is U2?").means], ["U2", "U2 is the move along y."]);
  assert.match(lines("what does zsymm mean").means, /holds z and the tilts about x and y/);
  assert.equal(lines("what is CF3?").means, "CF3 is a concentrated force along z.");
  assert.equal(lines("what does a pinned support mean").title, "Pinned");
});

test("a request to add a boundary condition, a load, a partition, a step or an interaction names the term; other requests do not (ADR-0110)", () => {
  const added = (text: string) => setupAsked(text)?.id ?? null;
  assert.equal(added("add a boundary condition"), "boundary-condition");
  assert.equal(added("Apply a BC on the left edge"), "boundary-condition");
  assert.equal(added("please add an encastre to the bottom"), "encastre");
  assert.equal(added("apply a pressure of 0.1 MPa"), "pressure");
  assert.equal(added("create a step"), "step");
  assert.equal(added("add contact between the plies"), "interaction");
  assert.equal(added("partition the coupon at the middle"), "partition");
  assert.equal(added("Can you add a load?"), "load");
  for (const text of ["make it compression", "add a ply", "apply 10 kN", "set the element size to 2", "add a hole", "what is a load?"]) assert.equal(added(text), null, text);
  assert.equal(isConditionOrLoad(termNamed("xsymm")!), true);
  assert.equal(isConditionOrLoad(termNamed("partition")!), false);
});
