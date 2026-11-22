"use client";

import { useEffect, useRef } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { FreeArea } from "@/components/workspace/canvas-slots";

/** How much of the part of the window left clear the model fills, across its tighter side: the mockup's (ADR-0134 amendment 1). */
const FILL = 0.92;
/** The home view's direction from the model: the mockup's, a little above the plate and along its length (ADR-0134 amendment 1). */
const HOME = new THREE.Vector3(0.44, -0.77, 0.47).normalize();
const TOP = new THREE.Vector3(0, -1e-3, 1).normalize(); // a hair off the vertical, so "up" (z) still turns the view

/** Where the camera stands to see a box from `dir` (z up) so that the box's picture fills `fx` of the view's half width or `fy` of its half
 * height, whichever is tighter, with the picture's middle at the view's middle: the target moved across the view and the distance scaled
 * until both hold (a few rounds settle it, as the mockup's fit does). */
export function fitView(dir: THREE.Vector3, centre: THREE.Vector3, corners: THREE.Vector3[], fovDeg: number, aspect: number, fx: number, fy: number):
  { target: THREE.Vector3; distance: number } {
  const z = dir.clone().normalize();
  const x = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 0, 1), z);
  if (x.lengthSq() < 1e-12) x.set(1, 0, 0);
  x.normalize();
  const y = new THREE.Vector3().crossVectors(z, x);
  const t = Math.tan(THREE.MathUtils.degToRad(fovDeg / 2));
  const target = centre.clone();
  let distance = 1;
  for (const c of corners) distance = Math.max(distance, 4 * c.distanceTo(centre));
  for (let round = 0; round < 8; round++) {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const corner of corners) {
      const d = corner.clone().sub(target);
      const depth = Math.max(distance - d.dot(z), 1e-6);
      const px = d.dot(x) / (depth * t * aspect), py = d.dot(y) / (depth * t);
      x0 = Math.min(x0, px); x1 = Math.max(x1, px); y0 = Math.min(y0, py); y1 = Math.max(y1, py);
    }
    target.addScaledVector(x, ((x0 + x1) / 2) * distance * t * aspect).addScaledVector(y, ((y0 + y1) / 2) * distance * t);
    distance *= Math.max((x1 - x0) / 2 / fx, (y1 - y0) / 2 / fy);
  }
  return { target, distance };
}

/** Frames the model in the part of the window the floating panels leave clear (ADR-0134 amendment 1): the projection's middle moved to
 * that part's middle (a view offset, so a turn or a zoom still turns about the model), and the camera put at the distance that fits the
 * model's box in it. It frames again each time `at` changes (the view buttons, a model of another size), and when the clear part changes
 * size while the engineer has not turned or zoomed the view themselves. Without a shell it frames in the whole canvas. */
export function FitCamera({ at, view, min, max, free }: {
  at: string; view: "home" | "top"; min: readonly [number, number, number]; max: readonly [number, number, number]; free: FreeArea | null;
}) {
  const { camera, controls, size, invalidate } = useThree();
  const moved = useRef(false);
  const framed = useRef("");
  useEffect(() => {
    const orbit = controls as unknown as THREE.EventDispatcher<{ start: object }> | null;
    if (!orbit?.addEventListener) return;
    const onStart = () => { moved.current = true; };
    orbit.addEventListener("start", onStart);
    return () => orbit.removeEventListener("start", onStart);
  }, [controls]);
  const freeKey = free ? `${free.left},${free.right},${free.top},${free.bottom}` : "";
  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera;
    const W = size.width, H = size.height;
    if (!(W > 0 && H > 0) || !cam.isPerspectiveCamera) return;
    const room = free && W - free.left - free.right > 80 && H - free.top - free.bottom > 80 ? free : null;
    if (room) {
      const cx = (room.left + W - room.right) / 2, cy = (room.top + H - room.bottom) / 2;
      cam.setViewOffset(W, H, W / 2 - cx, H / 2 - cy, W, H);
    } else cam.clearViewOffset();
    cam.aspect = W / H;
    cam.updateProjectionMatrix();
    const again = framed.current !== at;
    if (again || !moved.current) {
      const centre = new THREE.Vector3((min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2);
      const corners: THREE.Vector3[] = [];
      for (const cx of [min[0], max[0]]) for (const cy of [min[1], max[1]]) for (const cz of [min[2], max[2]]) corners.push(new THREE.Vector3(cx, cy, cz));
      const fx = FILL * (room ? (W - room.left - room.right) / W : 1);
      const fy = FILL * (room ? (H - room.top - room.bottom) / H : 1);
      const dir = view === "top" ? TOP : HOME;
      const { target, distance } = fitView(dir, centre, corners, cam.fov, cam.aspect, fx, fy);
      cam.position.copy(target).addScaledVector(dir, distance);
      cam.up.set(0, 0, 1);
      cam.lookAt(target);
      cam.far = Math.max(cam.far, distance * 4);
      cam.updateProjectionMatrix();
      const orbit = controls as unknown as { target: THREE.Vector3; update(): void } | null;
      if (orbit?.target) { orbit.target.copy(target); orbit.update(); }
      framed.current = at;
      if (again) moved.current = false;
    }
    invalidate();
  }, [at, freeKey, size.width, size.height, controls]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}
