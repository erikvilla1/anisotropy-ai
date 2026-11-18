import { test, expect } from "@playwright/test";

// The team band (components/team-band.tsx): who the team is, the programme it is part of, and the five portraits. It is
// the About page's last section since ADR-0077 amendment 73; until then it stood on the home page, and these cases were
// in tests/browser/home.spec.ts.

test("the team band is About's last section: one light grey block, its head across the page over the five portraits (ADR-0077 amendments 59, 61, 64, 65 and 73)", async ({ page }) => {
  await page.goto("/about");
  await expect(page.locator("#team")).toHaveCount(1);
  expect(await page.locator("main > *").last().evaluate((last) => last.id)).toBe("team");
  await page.locator("#team").scrollIntoViewIfNeeded();
  // The team band is one light grey block from edge to edge: its head has no ground of its own, and the portraits stand
  // close under it on the same grey (amendment 59, which ended amendment 41's grey head over white).
  const team = await page.locator("#team").evaluate((band) => {
    const head = band.querySelector(".band-head")!;
    const frame = band.querySelector(".team-face-frame")!;
    const box = band.getBoundingClientRect();
    return {
      band: getComputedStyle(band).backgroundColor, head: getComputedStyle(head).backgroundColor, left: box.left, right: box.right, wide: document.documentElement.clientWidth,
      gap: frame.getBoundingClientRect().top - head.getBoundingClientRect().bottom, framesInside: frame.getBoundingClientRect().bottom < box.bottom,
    };
  });
  expect(team.band).toBe("rgb(243, 243, 244)");
  expect(team.head).toBe("rgba(0, 0, 0, 0)");
  expect([team.left, team.right]).toEqual([0, team.wide]);
  expect(team.framesInside).toBe(true);
  expect(team.gap).toBeGreaterThan(0);
  expect(team.gap).toBeLessThan(80); // the head and the portraits are one block
  // Names and titles on the grey keep 4.5 to 1.
  const faceTones = await page.locator("#team .team-face").first().evaluate((card) => ({ name: getComputedStyle(card.querySelector("h3")!).color, title: getComputedStyle(card.querySelector("p")!).color }));
  const lightOf = (colour: string) => {
    const [red, green, blue] = colour.match(/[\d.]+/g)!.slice(0, 3).map((value) => { const share = Number(value) / 255; return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  for (const [name, colour] of Object.entries(faceTones)) expect((lightOf("rgb(243, 243, 244)") + 0.05) / (lightOf(colour) + 0.05), name).toBeGreaterThanOrEqual(4.5);
  // The head spans the page as the portraits do (amendment 61): the band's label over its heading at the portraits' left
  // edge, and from the halfway line who the team is and the programme it is part of. Nothing of how the team is run, and no
  // one's degree by name.
  const teamHead = page.locator("#team .band-head");
  await expect(teamHead.locator(".band-label")).toHaveText("Team");
  await expect(teamHead.getByRole("heading", { level: 2 })).toHaveText("From university to industry.");
  await expect(teamHead.locator(".team-band-text p").first()).toHaveText(
    "Five engineers trained in structures and mechanics: two are pursuing PhDs in structural engineering, two hold a BS in structural engineering and one a BS in mechanical engineering. Between them they cover modeling and validation, fabrication and mechanical testing, and the software and AI that connect them.",
  );
  // The Basement's mark stands beside the cohort, once, with its name for a screen reader, drawn in black (ADR-0081 amendment 3).
  await expect(teamHead.locator(".team-band-cohort span")).toHaveText("Part of the Fall 2026 Launchpad cohort");
  const mark = teamHead.locator("img");
  await expect(mark).toHaveCount(1);
  await expect(mark).toHaveAttribute("alt", "UC San Diego, The Basement");
  await expect(mark).toHaveAttribute("src", "/assets/partners/uc-san-diego-the-basement.png");
  await expect(mark).toHaveCSS("filter", "brightness(0)");
  await mark.scrollIntoViewIfNeeded();
  await expect.poll(() => mark.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(684);
  expect(await mark.evaluate((image) => Math.round(image.getBoundingClientRect().height))).toBe(46);
  await expect(page.locator("img[src*='uc-san-diego-the-basement']")).toHaveCount(1);
  await expect(teamHead).not.toContainText(/seats?\b|decides|spending|repository|\bCEO\b/i);
  await expect(page.locator("#team .team-faces-label")).toHaveCount(0);
  await expect(page.locator("#team .team-faces")).not.toContainText(/PhD|\bBS\b/);
  const placed = await page.locator("#team").evaluate((band) => {
    const box = (selector: string) => band.querySelector(selector)!.getBoundingClientRect();
    const words = (selector: string) => {
      const range = document.createRange();
      range.selectNodeContents(band.querySelector(selector)!);
      return range.getBoundingClientRect();
    };
    return {
      label: words(".band-head .band-label"), heading: words(".band-head h2"), text: box(".team-band-text"), head: box(".band-head"),
      frameLeft: Math.round(box(".team-face-frame").left), lastRight: Math.round([...band.querySelectorAll(".team-face-frame")].pop()!.getBoundingClientRect().right), wide: document.documentElement.clientWidth,
    };
  });
  expect(Math.round(placed.label.left)).toBe(32); // the page's margin
  expect(Math.round(placed.heading.left)).toBe(32);
  expect(placed.label.bottom).toBeLessThan(placed.heading.top);
  expect(Math.abs(placed.text.left - placed.wide / 2)).toBeLessThanOrEqual(20); // from the halfway line
  expect(Math.round(placed.text.right)).toBeLessThanOrEqual(placed.wide - 32 + 1);
  expect(placed.text.bottom).toBeLessThanOrEqual(placed.head.bottom + 1);
  // The five portraits stand in the band's middle and take about three quarters of its width, not all of it (amendment 64).
  const row = placed.lastRight - placed.frameLeft;
  expect(Math.abs((placed.frameLeft + placed.lastRight) / 2 - placed.wide / 2)).toBeLessThanOrEqual(2);
  expect(row).toBeGreaterThanOrEqual(Math.min(1180, placed.wide - 64) - 1);
  expect(row).toBeLessThanOrEqual(Math.max(0.76 * placed.wide, 1180) + 1);
  expect(row).toBeLessThan(placed.wide - 64 + 1);
  // The names carry no arrow, and nothing of the old cards of names and seats is left on the page.
  await expect(page.locator("#team .team-face h3 svg")).toHaveCount(0);
  await expect(page.locator(".team-card")).toHaveCount(0);
  await expect(page.locator("main")).not.toContainText(/two seats each/i);
});

test("the team's cards show the five portraits in the lead's order, and under the pointer the portrait lifts and LinkedIn's mark comes up as a link (ADR-0077 amendments 29 and 35)", async ({ page }) => {
  await page.goto("/about");
  const cards = page.locator("#team .team-face");
  await cards.first().scrollIntoViewIfNeeded();
  await expect(cards.locator("h3")).toHaveText(["Christopher Valerio", "Erik Villa", "Tabassum Zaman", "Jusung Park", "Kai Saucedo"]);
  // Under each name, one short line (amendment 43).
  await expect(cards.locator("h3 + p")).toHaveText(["Co-Founder, CEO", "Co-Founder, AI Lead", "Fabrication & Test Lead", "Simulation & Validation Lead", "Software & Growth Engineer"]);
  expect(await cards.locator("h3 + p").evaluateAll((lines) => lines.map((line) => Math.round(line.getBoundingClientRect().height)))).toEqual([24, 24, 24, 24, 24]);
  // Every frame holds a portrait that has loaded, from the site's own files, and no initials.
  await expect.poll(() => cards.locator("img").evaluateAll((images) => images.map((image) => (image as HTMLImageElement).naturalWidth))).toEqual([800, 800, 800, 800, 800]);
  expect(await cards.locator("img").evaluateAll((images) => images.every((image) => new URL((image as HTMLImageElement).src).pathname.startsWith("/assets/team/")))).toBe(true);
  await expect(cards.locator(".team-face-frame > span:not(.team-face-in)")).toHaveCount(0);
  // The mark is drawn in the frame's bottom right corner only for the card under the pointer, where the portrait also lifts.
  const badge = (index: number) => cards.nth(index).locator(".team-face-in");
  await expect(badge(2)).toHaveCSS("opacity", "0");
  await cards.nth(2).hover();
  await expect(badge(2)).toHaveCSS("opacity", "1");
  await expect(badge(0)).toHaveCSS("opacity", "0");
  await expect(badge(2)).toHaveCSS("border-radius", "50%");
  // The mark is the picture the lead uploaded, drawn in black and white (amendment 39).
  expect(await badge(2).evaluate((mark) => getComputedStyle(mark).backgroundImage)).toContain("/assets/brand/round-linkedin-logo");
  expect(await badge(2).evaluate((mark) => getComputedStyle(mark).filter)).toContain("grayscale(1)");
  const corner = await cards.nth(2).evaluate((card) => {
    const frame = card.querySelector(".team-face-frame")!.getBoundingClientRect();
    const mark = card.querySelector(".team-face-in")!.getBoundingClientRect();
    return [Math.round(frame.right - mark.right), Math.round(frame.bottom - mark.bottom)];
  });
  expect(corner[0]).toBeLessThanOrEqual(14);
  expect(corner[1]).toBeLessThanOrEqual(14);
  expect(await cards.nth(2).locator(".team-face-frame").evaluate((frame) => getComputedStyle(frame).transform)).not.toBe("none");
  expect(await cards.nth(0).locator(".team-face-frame").evaluate((frame) => getComputedStyle(frame).transform)).toBe("none");
  // The badge and the name both go to that person's LinkedIn profile, in a new tab (amendment 35).
  const profiles = ["christopher-valerio-916116225", "erik-villa-4b329b261", "tabassum-zaman-51659a264", "jusung-park-a46b43226", "kaisaucedo"];
  for (let index = 0; index < profiles.length; index++) {
    const address = new RegExp(`^https://www\\.linkedin\\.com/in/${profiles[index]}/$`);
    await expect(cards.nth(index).locator("a.team-face-in")).toHaveAttribute("href", address);
    await expect(cards.nth(index).locator("a.team-face-in")).toHaveAttribute("target", "_blank");
    await expect(cards.nth(index).locator("a.team-face-in")).toHaveAttribute("rel", /noopener/);
    await expect(cards.nth(index).locator("h3 a")).toHaveAttribute("href", address);
  }
  // Black with the mark in white; white with the mark in black under the pointer itself.
  expect(await badge(2).evaluate((mark) => getComputedStyle(mark).filter)).not.toContain("invert");
  await badge(2).hover();
  await expect.poll(() => badge(2).evaluate((mark) => getComputedStyle(mark).filter)).toContain("invert(1)");
});

