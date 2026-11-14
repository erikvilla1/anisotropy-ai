/** The site header's rule while the page scrolls: it leaves as the page goes down and comes back as soon as the page goes up,
 * wherever the page is, as a black bar fixed to the window's top. This file decides; it touches no page.
 * components/site-shell.tsx listens to the page, asks here, and writes the answer on the header as `data-scroll`;
 * app/globals.css draws it.
 *
 * At the page's top the header is "top": in the page's flow, where it always was, and it scrolls away with the page. Once
 * the whole of it has left the window it is "away": fixed above the window's top edge, out of sight, put there without a
 * move. A scroll up makes it "shown" and it slides down into the window; a scroll down makes it "hidden" and it slides back
 * up. "away" and "hidden" are the same place; only the second is seen going there. Back at the page's top it is "top" again. */
export type HeaderScroll = "top" | "away" | "shown" | "hidden";

/** What is kept from one event to the next: the state, and the mark, a scroll position in pixels. While the header is out
 * of sight the mark is the lowest the page has been; while it shows, the highest. The page must come back from the mark
 * by TURN_PX before the header answers. */
export type HeaderMemory = { state: HeaderScroll; mark: number };

/** The header where every page starts. */
export const AT_TOP: HeaderMemory = { state: "top", mark: 0 };

/** How far the page must go the other way before the header answers, in pixels. A coasting trackpad and a resting finger
 * move the page a pixel or two back and forth, and that is not a change of direction. */
export const TURN_PX = 8;

/** What the page says when it scrolls. */
export type HeaderPage = {
  /** How far the page is scrolled, in pixels. */
  y: number;
  /** The header's height, in pixels. */
  height: number;
  /** A menu of the header is open: the folded navigation, or the Services panel. */
  expanded: boolean;
  /** The keyboard's focus is inside the header. */
  focused: boolean;
  /** A script is moving the page or holding it still, not the visitor: a stage that takes the scroll over has locked the
   * page (components/home/tour-driver.ts), and what scrolls then is the stage putting the page back on its line. */
  scripted: boolean;
};

/** The header after the page has scrolled. */
export function headerAfterScroll(memory: HeaderMemory, page: HeaderPage): HeaderMemory {
  const { y } = page;
  // At the page's top it is the header it always was, whatever else is true.
  if (y <= 0) return AT_TOP;
  const { state } = memory;
  // An open menu hangs from the header: nothing changes while it is open, and the scroll is not counted afterwards.
  if (page.expanded) return { state, mark: y };
  if (state === "top") {
    // In the page's flow until the whole of it is above the window. With the keyboard's focus inside, it comes straight back.
    if (y < page.height) return { state, mark: y };
    return { state: page.focused ? "shown" : "away", mark: y };
  }
  // The keyboard's focus is never left out of sight.
  if (page.focused) return { state: "shown", mark: y };
  // A move down sends the bar away whoever makes it: a script takes the page down because the visitor asked.
  if (state === "shown") {
    const highest = Math.min(memory.mark, y);
    return y - highest >= TURN_PX ? { state: "hidden", mark: y } : { state, mark: highest };
  }
  // A script's move never brings the bar in, and is not counted afterwards.
  if (page.scripted) return { state, mark: y };
  const lowest = Math.max(memory.mark, y);
  return lowest - y >= TURN_PX ? { state: "shown", mark: y } : { state, mark: lowest };
}

/** The header after a stage has locked the page: a step plays on a stage that holds the whole window, and no scroll will
 * come to send a bar that shows away, so it goes now. A bar with an open menu, or with the keyboard's focus in it, stays. */
export function headerAfterLock(memory: HeaderMemory, page: Pick<HeaderPage, "y" | "expanded" | "focused">): HeaderMemory {
  if (memory.state !== "shown" || page.expanded || page.focused) return memory;
  return { state: "hidden", mark: page.y };
}

/** The header after the focus has come into it: it shows. Only while part of it is still in the window, in the page's
 * flow, is it left alone: the browser scrolls the rest of it in. */
export function headerAfterFocus(memory: HeaderMemory, page: Pick<HeaderPage, "y" | "height">): HeaderMemory {
  const { y } = page;
  if (y <= 0) return AT_TOP;
  if (memory.state === "top" && y < page.height) return memory;
  return { state: "shown", mark: y };
}
