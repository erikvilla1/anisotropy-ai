import * as THREE from "three";

/**
 * The material of one ply in the laminate view: unidirectional carbon prepreg, drawn by three.js's physical material with a
 * procedural fibre pattern written into its shader, so no image is downloaded and the pattern is sharp at any size.
 *
 * The pattern is a solid one: it is a function of the position inside the ply, measured across the fibres, through the thickness
 * and (stretched) along the fibres. The ply's faces therefore show tows and fibres running at the ply's real angle, a cut edge
 * that meets the fibres end-on shows their ends as a fine speckle, and a cut edge the fibres run along shows them as streaks.
 * The reflection is anisotropic about the same direction, under a clear resin coat.
 *
 * What identifies a ply is its angle colour (the swatch in the ply list): a thin line along the ply's cut edges and a restrained
 * tint of its reflection. Everything that changes while the view runs (angle, colour, size, hover, mark, dimming, opacity) is a
 * uniform, so nothing is rebuilt or recompiled per frame, and every ply shares one compiled program.
 */
export type PlyUniforms = {
  /** The ply's drawn size along x, y and z, in scene units. */
  uSize: { value: THREE.Vector3 };
  /** (cos θ, sin θ): the fibre direction, counterclockwise from x seen from above (ADR-0004). */
  uFibre: { value: THREE.Vector2 };
  /** The ply's angle colour. */
  uTint: { value: THREE.Color };
  /** x: hover, 0 to 1. y: marked, 0 to 1. z: dimmed, 0 to 1. w: a seed, so that two plies never show the same fibres. */
  uState: { value: THREE.Vector4 };
};
export type PlyMaterial = THREE.MeshPhysicalMaterial & { userData: { ply: PlyUniforms } };

const VERTEX_PARS = /* glsl */ `
uniform vec3 uSize;
varying vec3 vPly;
varying vec3 vPlyN;
varying vec3 vAxX;
varying vec3 vAxY;
varying vec3 vAxZ;
`;

// The mesh is a unit box scaled to the ply, so the position times the size is the position in the ply's own frame, in scene units;
// the frame's axes are carried to the fragment shader in view space, where the lighting is computed.
const VERTEX_MAIN = /* glsl */ `
vPly = position * uSize;
vPlyN = normal;
vAxX = normalize( ( modelViewMatrix * vec4( 1.0, 0.0, 0.0, 0.0 ) ).xyz );
vAxY = normalize( ( modelViewMatrix * vec4( 0.0, 1.0, 0.0, 0.0 ) ).xyz );
vAxZ = normalize( ( modelViewMatrix * vec4( 0.0, 0.0, 1.0, 0.0 ) ).xyz );
`;

const FRAGMENT_PARS = /* glsl */ `
uniform vec3 uSize;
uniform vec2 uFibre;
uniform vec3 uTint;
uniform vec4 uState;
varying vec3 vPly;
varying vec3 vPlyN;
varying vec3 vAxX;
varying vec3 vAxY;
varying vec3 vAxZ;

// The width of one tow on a ply's face, the two scales of the fibre pattern (1 / period) and how much longer than wide its features are.
#define CARBON_TOW 0.0215
#define CARBON_F1 118.0
#define CARBON_F2 290.0
#define CARBON_STRETCH 0.016

float plyHash( vec2 p ) {
	vec3 p3 = fract( vec3( p.xyx ) * 0.1031 );
	p3 += dot( p3, p3.yzx + 33.33 );
	return fract( ( p3.x + p3.y ) * p3.z );
}
float plyHash3( vec3 p3 ) {
	p3 = fract( p3 * 0.1031 );
	p3 += dot( p3, p3.zyx + 31.32 );
	return fract( ( p3.x + p3.y ) * p3.z );
}
float plyNoise( vec2 p ) {
	vec2 i = floor( p );
	vec2 f = fract( p );
	f = f * f * ( 3.0 - 2.0 * f );
	return mix( mix( plyHash( i ), plyHash( i + vec2( 1.0, 0.0 ) ), f.x ), mix( plyHash( i + vec2( 0.0, 1.0 ) ), plyHash( i + vec2( 1.0, 1.0 ) ), f.x ), f.y );
}
float plyNoise3( vec3 p ) {
	vec3 i = floor( p );
	vec3 f = fract( p );
	f = f * f * ( 3.0 - 2.0 * f );
	float a = mix( mix( plyHash3( i ), plyHash3( i + vec3( 1.0, 0.0, 0.0 ) ), f.x ), mix( plyHash3( i + vec3( 0.0, 1.0, 0.0 ) ), plyHash3( i + vec3( 1.0, 1.0, 0.0 ) ), f.x ), f.y );
	float b = mix( mix( plyHash3( i + vec3( 0.0, 0.0, 1.0 ) ), plyHash3( i + vec3( 1.0, 0.0, 1.0 ) ), f.x ), mix( plyHash3( i + vec3( 0.0, 1.0, 1.0 ) ), plyHash3( i + vec3( 1.0, 1.0, 1.0 ) ), f.x ), f.y );
	return mix( a, b, f.z );
}
vec3 plyToView( vec3 v ) {
	return normalize( v.x * vAxX + v.y * vAxY + v.z * vAxZ );
}
`;

// After the base colour: where the fragment is in the ply, what the fibres do there, and the colour that follows.
const FRAGMENT_COLOR = /* glsl */ `
vec3 plyN = normalize( vPlyN );
vec3 plyFibre = vec3( uFibre, 0.0 );
float plyFace = abs( plyN.z ); // 1 on the ply's two faces, 0 on its cut edges
float plyEndOn = abs( dot( plyN, plyFibre ) ); // 1 where the surface cuts the fibres square
vec3 plyAcross = cross( plyN, plyFibre ); // in the surface, across the fibres; its length says how far the fibres lie in the surface
float plySideOn = length( plyAcross );
float plyA = dot( vPly.xy, vec2( - uFibre.y, uFibre.x ) );
float plyL = dot( vPly.xy, uFibre );
float plySeed = uState.w;
float plyLit = max( uState.x, uState.y );

// Tows, on the faces: bands of slightly different tone with a fine seam between them, crowned a little across their width.
float towC = plyA / CARBON_TOW + plySeed * 7.31;
float towF = fract( towC );
float towR = plyHash( vec2( floor( towC ), plySeed ) );
float towW = fwidth( towC );
float towShown = plyFace * ( 1.0 - smoothstep( 0.22, 0.6, towW ) );
float towSeam = towShown * ( 1.0 - smoothstep( 0.045 - towW, 0.045 + towW, min( towF, 1.0 - towF ) ) );

// Fibres: a solid pattern, fine across the fibres and through the thickness, long along them, faded out before it would alias.
// (finer on a cut edge, where single fibres are what there is to see)
vec3 plyQ = vec3( plyA, vPly.z, plyL * CARBON_STRETCH ) * mix( 2.3, 1.0, plyFace );
vec3 plyQw = fwidth( plyQ );
float plyFoot = max( plyQw.x, max( plyQw.y, plyQw.z ) );
float plyFine = mix( 0.5, plyNoise3( plyQ * CARBON_F1 + plySeed * 3.1 ), 1.0 - smoothstep( 0.3, 0.8, plyFoot * CARBON_F1 ) );
#ifndef CARBON_LITE
	plyFine = mix( plyFine, mix( 0.5, plyNoise3( plyQ * CARBON_F2 + plySeed * 5.7 ), 1.0 - smoothstep( 0.3, 0.8, plyFoot * CARBON_F2 ) ), 0.45 );
#endif

// The slope of the surface across the fibres: each tow's crown, and a slow waviness of the whole tape.
float plySlope = towShown * cos( 3.14159265 * towF ) * 0.05;
#ifndef CARBON_LITE
	plySlope += plyFace * ( plyNoise( vec2( plyA * 11.0 + plySeed, plyL * 0.9 ) ) - 0.5 ) * 0.06;
#endif

// The angle colour's line along the cut edges, a fixed share of the ply's height with a floor so that it survives in a thin ply.
float plyLineHalf = clamp( 0.07 * uSize.z, 0.0015, 0.0055 ) * ( 1.0 + 0.45 * plyLit );
float plyLineW = 0.75 * fwidth( vPly.z ) + 1e-6;
float plyLine = ( 1.0 - plyFace ) * ( 1.0 - smoothstep( plyLineHalf - plyLineW, plyLineHalf + plyLineW, abs( vPly.z ) ) );

// The distance to the nearest edge of this face, for the eased edge and for the outline of a hovered or marked ply.
vec3 plyEdge = 0.5 * uSize - abs( vPly );
vec3 plyInFace = 1.0 - abs( plyN );
float plyEdgeMin = min( mix( 1e3, plyEdge.x, plyInFace.x ), min( mix( 1e3, plyEdge.y, plyInFace.y ), mix( 1e3, plyEdge.z, plyInFace.z ) ) );
float plyOutline = 1.0 - smoothstep( 0.6, 1.6, plyEdgeMin / max( fwidth( plyEdgeMin ), 1e-6 ) );
float plyBevel = clamp( 0.14 * uSize.z, 0.0012, 0.0045 );
vec3 plyBevN = normalize( plyN + sign( vPly ) * ( 1.0 - smoothstep( vec3( 0.0 ), vec3( plyBevel ), plyEdge ) ) * plyInFace * mix( 0.45, 0.8, plyFace ) );

float plyTone = 1.0 + ( plyFine - 0.5 ) * mix( 1.5, 0.95, plyFace ) + towShown * ( towR - 0.5 ) * 0.24 - towSeam * 0.42;
// A cut edge is machined, not moulded: matt and lighter than the face, darker where the fibres are met end-on.
plyTone *= mix( 3.4 - 1.3 * plyEndOn, 1.0, plyFace );
vec3 plyBase = diffuseColor.rgb * plyTone;
vec3 plyHue = mix( vec3( 1.0 ), 0.45 + 2.0 * uTint, mix( 0.14, 0.17, plyFace ) + 0.3 * plyLit );
plyBase *= plyHue;
plyBase += ( 0.012 + 0.03 * uTint ) * plyLit;
diffuseColor.rgb = mix( plyBase, 0.55 * uTint, plyLine );
// How strongly this spot mirrors: bundle by bundle on the faces, so the fibres read in the reflection itself.
float plyGloss = ( 0.5 + 1.0 * plyFine ) * ( 1.0 + towShown * ( towR - 0.5 ) * 0.8 ) * ( 1.0 - 0.7 * towSeam );
`;

const FRAGMENT_ROUGHNESS = /* glsl */ `
roughnessFactor = clamp( roughnessFactor + ( plyFine - 0.5 ) * 0.24 + towSeam * 0.14 + plyEndOn * 0.2 + plyLine * 0.25, 0.08, 1.0 );
metalnessFactor *= 1.0 - plyLine;
`;

const FRAGMENT_NORMAL = /* glsl */ `
normal = plyToView( plyBevN + plyAcross * plySlope );
`;

const FRAGMENT_CLEARCOAT_NORMAL = /* glsl */ `
#ifdef USE_CLEARCOAT
	clearcoatNormal = plyToView( plyBevN );
#endif
`;

const FRAGMENT_EMISSIVE = /* glsl */ `
totalEmissiveRadiance += uTint * plyLine * ( 0.7 + 1.6 * plyLit );
totalEmissiveRadiance += mix( uTint, vec3( 1.0 ), 0.72 ) * plyOutline * ( 0.9 * uState.x + 1.25 * uState.y );
totalEmissiveRadiance += uTint * ( 0.035 * uState.x + 0.11 * uState.y );
`;

// The reflection is stretched across the fibres (the bitangent is the fibre direction as it lies in the surface), and not at all
// where the surface meets the fibres end-on.
const FRAGMENT_ANISOTROPY = /* glsl */ `
#ifdef USE_ANISOTROPY
	material.anisotropy = saturate( length( anisotropyVector ) * plySideOn * ( 1.0 - plyLine ) );
	material.alphaT = mix( pow2( material.roughness ), 1.0, pow2( material.anisotropy ) );
	vec3 plyB = plySideOn > 1e-3 ? ( plyFibre - plyN * dot( plyN, plyFibre ) ) / plySideOn : normalize( cross( plyN, vec3( 0.0, 0.0, 1.0 ) ) );
	material.anisotropyB = plyToView( plyB );
	material.anisotropyT = plyToView( cross( plyN, plyB ) );
#endif
material.specularColor *= plyGloss * plyHue;
material.specularColorBlended *= plyGloss * plyHue;
#ifdef USE_CLEARCOAT
	material.clearcoat *= mix( 0.2, 1.0, plyFace ) * ( 1.0 - plyLine );
#endif
`;

const FRAGMENT_DIM = /* glsl */ `
outgoingLight *= 1.0 - 0.45 * uState.z;
`;

function after(source: string, chunk: string, addition: string): string {
  const include = `#include <${chunk}>`;
  if (!source.includes(include)) throw new Error(`The physical material's shader has no ${include}: the carbon pattern cannot be written into it.`);
  return source.replace(include, `${include}\n${addition}`);
}
function before(source: string, chunk: string, addition: string): string {
  const include = `#include <${chunk}>`;
  if (!source.includes(include)) throw new Error(`The physical material's shader has no ${include}: the carbon pattern cannot be written into it.`);
  return source.replace(include, `${addition}\n${include}`);
}

/**
 * How much of the look a device is given. `full`: everything. `lite`, for phones: without the finest fibre scale and the tape's
 * waviness. `plain`, for a browser that draws WebGL in software or cannot hold a frame rate: `lite` without the resin coat and the
 * stretched reflection, lit by lamps alone (the view mounts no environment map for it).
 */
export type CarbonGrade = "full" | "lite" | "plain";

/** One ply's material. */
export function createPlyMaterial(grade: CarbonGrade): PlyMaterial {
  const lite = grade !== "full";
  const plain = grade === "plain";
  const ply: PlyUniforms = {
    uSize: { value: new THREE.Vector3(1, 1, 1) },
    uFibre: { value: new THREE.Vector2(1, 0) },
    uTint: { value: new THREE.Color("#808080") },
    uState: { value: new THREE.Vector4(0, 0, 0, 0) },
  };
  const material = new THREE.MeshPhysicalMaterial({
    color: "#2b2c2f",
    roughness: 0.5,
    metalness: 0.12,
    ior: 1.8,
    clearcoat: plain ? 0 : 0.5,
    clearcoatRoughness: 0.26,
    anisotropy: plain ? 0 : 0.8,
    envMapIntensity: 1,
    dithering: true,
    // Blended while staying in the opaque pass: a ply that is fading in is drawn last (its renderOrder), over the plies under it,
    // and a laid ply's opacity of 1 makes the blend a plain write. No program is swapped when a ply starts or stops fading.
    blending: THREE.CustomBlending,
    blendSrc: THREE.SrcAlphaFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
  }) as PlyMaterial;
  material.userData.ply = ply;
  material.defines = { ...material.defines, ...(lite ? { CARBON_LITE: "" } : {}) };
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, ply);
    shader.vertexShader = after(after(shader.vertexShader, "common", VERTEX_PARS), "begin_vertex", VERTEX_MAIN);
    let fragment = after(shader.fragmentShader, "common", FRAGMENT_PARS);
    fragment = after(fragment, "color_fragment", FRAGMENT_COLOR);
    fragment = after(fragment, "metalnessmap_fragment", FRAGMENT_ROUGHNESS);
    fragment = after(fragment, "normal_fragment_maps", FRAGMENT_NORMAL);
    fragment = after(fragment, "clearcoat_normal_fragment_maps", FRAGMENT_CLEARCOAT_NORMAL);
    fragment = after(fragment, "emissivemap_fragment", FRAGMENT_EMISSIVE);
    fragment = after(fragment, "lights_physical_fragment", FRAGMENT_ANISOTROPY);
    fragment = before(fragment, "opaque_fragment", FRAGMENT_DIM);
    shader.fragmentShader = fragment;
  };
  material.customProgramCacheKey = () => `carbon-ply-${grade}`;
  return material;
}
