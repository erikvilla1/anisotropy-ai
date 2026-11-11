import { test } from "node:test";
import assert from "node:assert/strict";
import { blankForm, buildValues, exampleForm } from "../lib/studio-form";
import { LIVE_DEBOUNCE_MS, liveKey, setupComplete, shouldSolveLive } from "../lib/studio-live";

// When the page asks our kernel for a live solve (ADR-0086); the page computes nothing, so only the moment of asking is decided here.
const ready = { api: true, complete: true, running: false, tow: false, key: "b", sent: "a" };

test("a complete setup whose rows changed is solved live; nothing else is", () => {
  assert.equal(shouldSolveLive(ready), true);
  assert.equal(shouldSolveLive({ ...ready, sent: "b" }), false, "the same rows are never sent twice");
  assert.equal(shouldSolveLive({ ...ready, complete: false }), false, "a row the setup needs is empty");
  assert.equal(shouldSolveLive({ ...ready, running: true }), false, "a full run is going");
  assert.equal(shouldSolveLive({ ...ready, tow: true }), false, "the fibre tow has no model");
  assert.equal(shouldSolveLive({ ...ready, api: false }), false, "the page has no API to ask");
  assert.equal(shouldSolveLive({ ...ready, sent: null }), true, "nothing sent yet");
  assert.ok(LIVE_DEBOUNCE_MS >= 300 && LIVE_DEBOUNCE_MS <= 1500, "a settled edit, not every keystroke");
});

test("the setup is complete once every step but the engineer's name is filled", () => {
  const example = exampleForm("2026-11-10");
  assert.equal(example.filled_by, "");
  assert.equal(setupComplete(example), true, "the public example needs no name to be solved live");
  assert.equal(setupComplete(blankForm()), false);
  assert.equal(setupComplete({ ...example, length: "" }), false);
  assert.equal(setupComplete({ ...example, value: "" }), false);
});

test("the rows' key changes with any row and only with the rows", () => {
  const example = exampleForm("2026-11-10");
  const key = liveKey(buildValues(example));
  assert.equal(liveKey(buildValues({ ...example })), key);
  assert.notEqual(liveKey(buildValues({ ...example, value: "0.5" })), key);
});
