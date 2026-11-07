"use client";

import { ContactShadows, Environment, Lightformer } from "@react-three/drei";

/**
 * Presentation lighting for the model (ADR-0063): a procedural room of light panels rendered once into an environment map, so the
 * cured surface of the coupon picks up soft reflections without downloading an image, and a blurred contact shadow under the part.
 * The scene is z-up (the plate lies in x and y, its thickness along z), so the panels sit above it and the shadow's floor is turned
 * from drei's y-up to our z-up. The results view uses none of this: its material is unlit (`field-material.ts`).
 */
export function PresentationLighting({ size, centre, floor }: { size: number; centre: readonly [number, number]; floor: number }) {
  return (
    <>
      <Environment resolution={256} frames={1}>
        <Lightformer form="rect" intensity={2.6} color="#f4f2ea" position={[2, -3, 7]} scale={[7, 7, 1]} />
        <Lightformer form="rect" intensity={1.1} color="#dfe8f5" position={[-6, 4, 4]} scale={[5, 3, 1]} />
        <Lightformer form="rect" intensity={0.7} color="#ececec" position={[5, 6, 2]} scale={[4, 3, 1]} />
        <Lightformer form="circle" intensity={0.35} color="#9f9f9f" position={[0, 0, -7]} scale={6} />
      </Environment>
      <directionalLight position={[size, -size, 2 * size]} intensity={0.45} />
      <group position={[centre[0], centre[1], floor]} rotation={[Math.PI / 2, 0, 0]}>
        <ContactShadows opacity={0.6} scale={[2 * size, 2 * size]} blur={2.4} far={0.5 * size} resolution={512} color="#000000" />
      </group>
    </>
  );
}

/** The material of the model in presentation mode: a cured composite's clearcoat over a matte base. */
export const PRESENTATION_MATERIAL = { color: "#808080", metalness: 0, roughness: 0.55, clearcoat: 0.9, clearcoatRoughness: 0.3 } as const;
