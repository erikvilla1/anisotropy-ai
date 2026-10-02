import { test } from "node:test";
import assert from "node:assert/strict";
import { physicsTopics } from "../lib/physics";
import { longitudinalMixture, thermalMixture, halpinTsai, planeStressQ, rotatedQ, transformations, multiplyVector, referenceABD, type Vector3 } from "../lib/physics-reference-checks";

const near = (actual: number, expected: number, tolerance: number) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} ≠ ${expected} ± ${tolerance}`);
const inputs = { E1: 145e9, E2: 10.5e9, G12: 7e9, nu12: .28 };
test("published textbook examples reproduce the printed answers", () => {
  near(longitudinalMixture(235, 4.14, .65), 154.2, .005); // Problem 5.2, GPa.
  const { A } = referenceABD(inputs, [0,45,-45].map(angleDeg => ({ angleDeg, thicknessM: .00025 })));
  [A[0][0], A[0][1], A[1][1], A[2][2]].forEach((v, i) => near(v / 1e6, [60.24,17.53,26.43,20.56][i], .005)); // Problem 7.11, MN/m.
  const cte = thermalMixture({ Ef: 69, Em: 3.8, Vf: .55, nuf: .22, num: .36, af: 4.5e-6, am: 90e-6 });
  near(cte.alpha1 * 1e6, 8.19, .005); near(cte.alpha2 * 1e6, 55.8, .05); // Problem 8.1, microstrain/K.
});
test("engineering-shear transforms preserve work and recover their inverse", () => {
  const stress: Vector3 = [120, -40, 17], strain: Vector3 = [.003, -.001, .004];
  const dot = (a: Vector3, b: Vector3) => a.reduce((sum, x, i) => sum + x*b[i], 0);
  for (const angle of [0, 30, 45, 90, -37]) {
    const t = transformations(angle), inverse = transformations(-angle);
    const localStress = multiplyVector(t.stress, stress), localStrain = multiplyVector(t.strain, strain);
    near(dot(localStress, localStrain), dot(stress, strain), 1e-12);
    multiplyVector(inverse.strain, localStrain).forEach((v, i) => near(v, strain[i], 1e-15));
    const q = rotatedQ(inputs, angle);
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) near(q[i][j], q[j][i], 1e-4);
  }
  const q = planeStressQ(inputs), q90 = rotatedQ(inputs, 90);
  near(q90[0][0], q[1][1], 1e-4); near(q90[1][1], q[0][0], 1e-4);
});
test("laminate coupling, thickness scaling and constituent limits are consistent", () => {
  const stack = (angles: number[], t = .00025) => referenceABD(inputs, angles.map(angleDeg => ({ angleDeg, thicknessM: t })));
  const symmetric = stack([0, 90, 90, 0]);
  symmetric.B.flat().forEach(v => near(v, 0, 1e-8));
  const unsymmetric = stack([0, 90]);
  assert.ok(Math.abs(unsymmetric.B[0][0]) > 1);
  const doubled = stack([0,90], .0005);
  near(doubled.A[0][0], 2 * unsymmetric.A[0][0], 1e-5);
  near(doubled.B[0][0], 4 * unsymmetric.B[0][0], 1e-8);
  near(doubled.D[0][0], 8 * unsymmetric.D[0][0], 1e-8);
  near(halpinTsai(70, 4, 0, 2), 4, 1e-12);
  near(halpinTsai(70, 4, 1, 2), 70, 1e-10);
  near(halpinTsai(70, 4, .6, 0), 1 / (.6/70 + .4/4), 1e-12);
  assert.throws(() => longitudinalMixture(70,4,60), /fraction/);
  assert.throws(() => planeStressQ({ ...inputs, nu12: 10 }), /compliance/);
  assert.throws(() => stack([0], 0), /positive/);
});
test("every current formula has a location and unit convention; future solver workflows are separate", () => {
  assert.equal(physicsTopics.flatMap(t => t.methods).length, 29);
  assert.ok(!physicsTopics.some(t => t.id === "fea" || t.id === "optimization"));
  for (const topic of physicsTopics) for (const method of topic.methods) {
    assert.ok(method.reference?.location && method.units);
    assert.match(method.reference.url, /^https:/);
  }
  const maxStrain = physicsTopics.flatMap(t => t.methods).find(m => m.name === "Maximum strain")!;
  assert.match(maxStrain.detail, /missing compression or shear/);
});
