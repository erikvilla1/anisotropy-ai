"use client";

import { useEffect, useRef } from "react";
import { graticule, nearRuns, turnMatrix, vectorsOf, type Place } from "./globe-math";
import "@/app/contact/contact-globe.css";

/** The place that faces the eye when the globe is first drawn: off North America's west coast, a little north of the
 * equator, so the globe is seen slightly from above and reads as a globe, not as a flat map on a disc. */
const START = { lon: -122, lat: 18 };
/** How fast the globe turns about its upright axis, in degrees a second: a whole turn in a minute. */
const DEGREES_A_SECOND = 6;
/** No more than this much of a turn is made in one frame, in seconds: a frame that was long, or a tab that was away. */
const LONGEST_FRAME = 0.05;
/** The canvas is drawn at the screen's own pixels, up to twice the page's. */
const MOST_PIXELS = 2;
/** The net of latitude and longitude under the coasts: a line every 30 degrees. */
const NET_STEP = 30;
/** Line widths in the page's pixels and how strongly each is drawn, in the element's text colour. */
const LAND = { width: 0.7, alpha: 0.9 };
const NET = { width: 0.5, alpha: 0.14 };
const EDGE = { width: 1.1, alpha: 0.85 };

/** The contact page's globe: the world's coasts and borders as thin lines on a sphere, turning slowly by itself, with the
 * sphere's outline round them. It is a picture and nothing more: hidden from assistive technology, it takes no pointer.
 *
 * It is drawn on a canvas in the element's own text colour, so the page that places it decides the colour. The lines are
 * lib/globe-land.json (scripts/globe-land.mjs says where they come from), loaded only when the globe is on a page; until they
 * are in, the outline and the net stand alone. The globe turns only while it is in the window and its tab is showing, and
 * a visitor who asks for reduced motion gets one still frame. */
export function ContactGlobe({ className }: { className?: string }) {
  const holder = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const box = holder.current;
    const sheet = canvas.current;
    const pen = sheet?.getContext("2d");
    if (!box || !sheet || !pen) return;

    const net = graticule(NET_STEP).map(vectorsOf);
    let land: Float32Array[] = [];
    let lon = START.lon;
    let frame = 0;
    let last = 0;
    let inWindow = false;
    let gone = false;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)");

    /** One frame: the net, the coasts and the outline, as the globe stands now. */
    const draw = () => {
      const size = sheet.width;
      if (!size) return;
      const scale = size / Math.max(1, box.clientWidth); // the canvas's pixels to one of the page's
      const middle = size / 2;
      const radius = middle - EDGE.width * scale;
      const matrix = turnMatrix({ lon, lat: START.lat });
      pen.clearRect(0, 0, size, size);
      pen.strokeStyle = getComputedStyle(box).color;
      pen.lineJoin = "round";
      pen.lineCap = "round";
      const stroke = (lines: Float32Array[], style: { width: number; alpha: number }) => {
        pen.globalAlpha = style.alpha;
        pen.lineWidth = style.width * scale;
        pen.beginPath();
        for (const line of lines) {
          for (const run of nearRuns(line, matrix)) {
            pen.moveTo(middle + run[0] * radius, middle - run[1] * radius);
            for (let index = 2; index < run.length; index += 2) pen.lineTo(middle + run[index] * radius, middle - run[index + 1] * radius);
          }
        }
        pen.stroke();
      };
      stroke(net, NET);
      stroke(land, LAND);
      pen.globalAlpha = EDGE.alpha;
      pen.lineWidth = EDGE.width * scale;
      pen.beginPath();
      pen.arc(middle, middle, radius, 0, 2 * Math.PI);
      pen.stroke();
      pen.globalAlpha = 1;
    };

    /** The canvas takes the holder's width, square, at the screen's pixels. */
    const fit = () => {
      const pixels = Math.round(box.clientWidth * Math.min(MOST_PIXELS, window.devicePixelRatio || 1));
      if (pixels > 0 && sheet.width !== pixels) sheet.width = sheet.height = pixels;
      draw();
    };

    const turn = (now: number) => {
      frame = 0;
      // The surface moves to the east, as the Earth's does, so the place that faces the eye moves west.
      lon -= DEGREES_A_SECOND * Math.min(LONGEST_FRAME, Math.max(0, (now - last) / 1000));
      if (lon < -180) lon += 360;
      last = now;
      draw();
      frame = window.requestAnimationFrame(turn);
    };
    /** Turning starts or stops with what the visitor can see: in the window, the tab showing, and motion not turned down. */
    const pace = () => {
      const turning = inWindow && document.visibilityState === "visible" && !still.matches;
      if (turning && !frame) {
        last = performance.now();
        frame = window.requestAnimationFrame(turn);
      } else if (!turning && frame) {
        window.cancelAnimationFrame(frame);
        frame = 0;
      }
    };

    const sized = new ResizeObserver(fit);
    sized.observe(box);
    const watched = new IntersectionObserver((entries) => {
      inWindow = entries[entries.length - 1].isIntersecting;
      pace();
    });
    watched.observe(box);
    document.addEventListener("visibilitychange", pace);
    still.addEventListener("change", pace);
    fit();

    import("@/lib/globe-land.json").then((record) => {
      if (gone) return;
      land = (record.default.lines as unknown as Place[][]).map(vectorsOf);
      draw();
    }, () => {
      // Without the lines the outline and the net stand alone.
    });

    return () => {
      gone = true;
      if (frame) window.cancelAnimationFrame(frame);
      sized.disconnect();
      watched.disconnect();
      document.removeEventListener("visibilitychange", pace);
      still.removeEventListener("change", pace);
    };
  }, []);

  return (
    <div ref={holder} className={className ? `contact-globe ${className}` : "contact-globe"} aria-hidden="true">
      <canvas ref={canvas} />
    </div>
  );
}
