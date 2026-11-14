import test from "node:test";
import assert from "node:assert/strict";
import { AT_TOP, TURN_PX, headerAfterFocus, headerAfterLock, headerAfterScroll, type HeaderMemory, type HeaderPage, type HeaderScroll } from "../components/header-scroll";

// The site header's rule on scroll (components/header-scroll.ts): it leaves as the page goes down and comes back as soon as
// the page goes up. Here the page is a list of scroll positions; no browser is involved.

const HEIGHT = 84;
const page = (y: number, more: Partial<HeaderPage> = {}): HeaderPage => ({ y, height: HEIGHT, expanded: false, focused: false, scripted: false, ...more });
/** The header after the page has been at each of these positions in turn, starting from the page's top. */
const after = (positions: number[], from: HeaderMemory = AT_TOP, more: Partial<HeaderPage> = {}) =>
  positions.reduce((memory, y) => headerAfterScroll(memory, page(y, more)), from);
/** The states the header goes through over these positions. */
const states = (positions: number[], from: HeaderMemory = AT_TOP): HeaderScroll[] => {
  let memory = from;
  return positions.map((y) => (memory = headerAfterScroll(memory, page(y))).state);
};

test("at the page's top the header is in the page's flow, and stays there until the whole of it has left the window", () => {
  assert.equal(AT_TOP.state, "top");
  assert.deepEqual(states([0, 10, 40, HEIGHT - 1]), ["top", "top", "top", "top"]);
  // Going back up before it has left changes nothing: it is still the page's own header.
  assert.deepEqual(states([60, 20, 60, 5]), ["top", "top", "top", "top"]);
  // Once it is whole above the window it is put away, without having been shown.
  assert.deepEqual(states([40, HEIGHT]), ["top", "away"]);
  assert.equal(after([2000]).state, "away"); // a jump down the page, as a link makes
});

test("a scroll up brings it back wherever the page is, and a scroll down sends it away again", () => {
  assert.deepEqual(states([500, 1500, 1490]), ["away", "away", "shown"]);
  assert.deepEqual(states([500, 1500, 1490, 1300, 1310]), ["away", "away", "shown", "shown", "hidden"]);
  // And back again, from where it was hidden: it need not have been at the top in between.
  assert.deepEqual(states([1500, 1400, 1450, 1440]), ["away", "shown", "hidden", "shown"]);
  // Hidden after having been shown is "hidden", never "away": the stylesheet slides the one and not the other.
  assert.equal(after([1500, 1400, 1500, 1600, 3000]).state, "hidden");
});

test("it takes a real change of direction: a pixel or two back and forth changes nothing", () => {
  assert.ok(TURN_PX >= 4 && TURN_PX <= 16);
  // Out of sight, the page trembles on its way down.
  assert.deepEqual(states([800, 798, 801, 799, 802, 800]), ["away", "away", "away", "away", "away", "away"]);
  // The distance is counted from the lowest point reached, not from the last event: slow scrolling up still counts.
  const slow = Array.from({ length: TURN_PX }, (_, step) => 800 - (step + 1));
  assert.deepEqual(states([800, ...slow]).slice(-2), ["away", "shown"]);
  // Shown, the page trembles; then a slow scroll down hides it, counted from the highest point reached.
  const shown = after([800, 700]);
  assert.equal(shown.state, "shown");
  assert.deepEqual(states([702, 699, 701, 698, 700], shown), ["shown", "shown", "shown", "shown", "shown"]);
  assert.equal(after([698 + TURN_PX - 1], after([698], shown)).state, "shown");
  assert.equal(after([698 + TURN_PX], after([698], shown)).state, "hidden");
});

test("back at the page's top it is the page's own header again, from any state", () => {
  for (const positions of [[2000], [2000, 1900], [2000, 1900, 2000]]) {
    const before = after(positions);
    assert.deepEqual(headerAfterScroll(before, page(0)), AT_TOP, before.state);
    // A phone's page springs past its top; that is the top too.
    assert.deepEqual(headerAfterScroll(before, page(-30)), AT_TOP, before.state);
  }
  // It stays fixed until the page is at its very top, where the fixed bar and the header in the flow are the same place.
  assert.equal(after([2000, 1900, 1]).state, "shown");
  // And from the top it leaves with the page again.
  assert.deepEqual(states([2000, 1900, 0, 30, HEIGHT + 1]), ["away", "shown", "top", "top", "away"]);
});

test("a script's move never brings the header in, and is not counted afterwards; a move down still sends it away", () => {
  const scripted = { scripted: true };
  // A stage that has locked the page puts it back on its line: the page goes up by more than a turn, and the header stays
  // out of sight.
  for (const out of [after([900]), after([900, 800, 900])]) {
    const held = after([850, 820, 900, 860], out, scripted);
    assert.equal(held.state, out.state);
    assert.equal(held.mark, 860);
    // The visitor's own scroll up afterwards is counted from where the script left the page.
    assert.equal(headerAfterScroll(held, page(860 - TURN_PX + 1)).state, out.state);
    assert.equal(headerAfterScroll(held, page(860 - TURN_PX)).state, "shown");
  }
  // The visitor went up a little and asks to go down again: a script carries the page down, and the bar goes.
  const shown = after([500, 400]);
  assert.equal(shown.state, "shown");
  assert.equal(after([430, 470, 500], shown, scripted).state, "hidden");
  // A script's small move up under a bar that shows changes nothing.
  assert.equal(after([395, 400], shown, scripted).state, "shown");
  // The header still leaves the page's flow on the way down, script or not: that is not seen.
  assert.equal(after([40, 500], AT_TOP, scripted).state, "away");
});

test("when a stage locks the page a bar that shows goes, unless a menu is open or the keyboard's focus is in it", () => {
  const shown = after([500, 400]);
  assert.deepEqual(headerAfterLock(shown, { y: 500, expanded: false, focused: false }), { state: "hidden", mark: 500 });
  assert.equal(headerAfterLock(shown, { y: 500, expanded: true, focused: false }), shown);
  assert.equal(headerAfterLock(shown, { y: 500, expanded: false, focused: true }), shown);
  // Out of sight, or at the page's top, there is nothing to send away.
  for (const memory of [AT_TOP, after([500]), after([500, 400, 500])]) {
    assert.equal(headerAfterLock(memory, { y: 500, expanded: false, focused: false }), memory);
  }
});

test("while a menu of the header is open nothing changes; at the page's top the header and its menu scroll with the page as before", () => {
  const expanded = { expanded: true };
  // Opened while the bar shows: scrolling down does not take the bar and its menu away.
  const shown = after([900, 800]);
  assert.equal(after([1500, 2500], shown, expanded).state, "shown");
  // Closed again, a scroll down hides it, counted from where the page then is.
  const closed = after([2500], shown, expanded);
  assert.equal(headerAfterScroll(closed, page(2500 + TURN_PX - 1)).state, "shown");
  assert.equal(headerAfterScroll(closed, page(2500 + TURN_PX)).state, "hidden");
  // Opened at the page's top: the header stays in the page's flow however far the page goes.
  assert.equal(after([50, 400, 300], AT_TOP, expanded).state, "top");
  // Once the menu is closed the next scroll puts the header away.
  assert.equal(headerAfterScroll(after([400], AT_TOP, expanded), page(410)).state, "away");
});

test("the keyboard's focus is never left out of sight: the header shows while the focus is inside it", () => {
  const focused = { focused: true };
  // Scrolling down with the focus in the header keeps the bar.
  const shown = after([900, 800]);
  assert.equal(after([1500, 2500], shown, focused).state, "shown");
  // From the page's top: in the flow while any of it is in the window, then straight back as the bar.
  assert.deepEqual([40, HEIGHT - 1, HEIGHT, 600].map((y) => after([y], AT_TOP, focused).state), ["top", "top", "shown", "shown"]);
  // Also while a script holds the page.
  assert.equal(headerAfterScroll(after([900]), page(900, { focused: true, scripted: true })).state, "shown");
  // Once the focus has left, it hides on the way down as usual.
  assert.equal(after([2500, 2600], after([1500], shown, focused)).state, "hidden");
});

test("the focus coming into a header that is out of sight shows it", () => {
  for (const positions of [[2000], [2000, 1900, 2000]]) {
    const before = after(positions);
    assert.notEqual(before.state, "shown");
    const then = headerAfterFocus(before, page(2000));
    assert.deepEqual(then, { state: "shown", mark: 2000 });
    // The scroll that follows is counted from there.
    assert.equal(headerAfterScroll(then, page(2000 + TURN_PX)).state, "hidden");
  }
  // At the page's top, and while part of the header is still in the window in the page's flow, nothing changes.
  assert.deepEqual(headerAfterFocus(AT_TOP, page(0)), AT_TOP);
  const partly = after([30]);
  assert.equal(headerAfterFocus(partly, page(30)), partly);
  // A header left in the flow under an open menu, now far above the window, shows as the bar.
  const left = after([400], AT_TOP, { expanded: true });
  assert.equal(headerAfterFocus(left, page(400)).state, "shown");
});
