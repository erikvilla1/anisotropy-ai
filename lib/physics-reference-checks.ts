/** Small numerical kernels for checking reference equations. Not a component solver. */
export type Vector3 = [number, number, number];
export type Matrix3 = [Vector3, Vector3, Vector3];
export type ElasticInputs = { E1: number; E2: number; G12: number; nu12: number };
const finite = (...values: number[]) => {
  if (!values.every(Number.isFinite)) throw new Error("Inputs must be finite");
};
const fraction = (value: number) => {
  finite(value);
  if (value < 0 || value > 1) throw new Error("Use a fraction between zero and one");
};
const positive = (...values: number[]) => {
  finite(...values);
  if (values.some(x => x <= 0)) throw new Error("Moduli and thicknesses must be positive");
};
export function longitudinalMixture(Ef: number, Em: number, Vf: number) {
  positive(Ef, Em); fraction(Vf);
  return Ef * Vf + Em * (1 - Vf);
}
export function halpinTsai(Pf: number, Pm: number, Vf: number, xi: number) {
  positive(Pf, Pm); fraction(Vf); finite(xi);
  if (xi < 0) throw new Error("This reference check requires nonnegative xi");
  const eta = (Pf / Pm - 1) / (Pf / Pm + xi);
  const denominator = 1 - eta * Vf;
  if (!(denominator > 0)) throw new Error("Invalid Halpin–Tsai denominator");
  return Pm * (1 + xi * eta * Vf) / denominator;
}
export function thermalMixture(p: { Ef: number; Em: number; Vf: number; nuf: number; num: number; af: number; am: number }) {
  finite(p.nuf, p.num, p.af, p.am);
  if ([p.nuf, p.num].some(nu => nu <= -1 || nu >= .5)) throw new Error("Use stable isotropic constituent Poisson ratios");
  const E1 = longitudinalMixture(p.Ef, p.Em, p.Vf);
  const Vm = 1 - p.Vf;
  const nu12 = p.nuf * p.Vf + p.num * Vm;
  const alpha1 = (p.Ef * p.af * p.Vf + p.Em * p.am * Vm) / E1;
  return { alpha1, alpha2: p.af * p.Vf * (1 + p.nuf) + p.am * Vm * (1 + p.num) - nu12 * alpha1 };
}
export function planeStressQ(p: ElasticInputs): Matrix3 {
  positive(p.E1, p.E2, p.G12); finite(p.nu12);
  const delta = 1 - p.nu12 ** 2 * p.E2 / p.E1;
  if (!(delta > 0)) throw new Error("Elastic inputs violate positive compliance");
  return [[p.E1 / delta, p.nu12 * p.E2 / delta, 0], [p.nu12 * p.E2 / delta, p.E2 / delta, 0], [0, 0, p.G12]];
}
export function transformations(angleDeg: number): { stress: Matrix3; strain: Matrix3 } {
  finite(angleDeg);
  const theta = angleDeg * Math.PI / 180;
  const m = Math.cos(theta), n = Math.sin(theta);
  return {
    stress: [[m*m, n*n, 2*m*n], [n*n, m*m, -2*m*n], [-m*n, m*n, m*m-n*n]],
    strain: [[m*m, n*n, m*n], [n*n, m*m, -m*n], [-2*m*n, 2*m*n, m*m-n*n]],
  };
}
export function multiplyVector(a: Matrix3, x: Vector3): Vector3 {
  return a.map(row => row.reduce((sum, v, j) => sum + v * x[j], 0)) as Vector3;
}
function multiply(a: Matrix3, b: Matrix3): Matrix3 {
  return a.map(row => [0, 1, 2].map(j => row.reduce((sum, v, k) => sum + v * b[k][j], 0))) as Matrix3;
}
export function rotatedQ(p: ElasticInputs, angleDeg: number): Matrix3 {
  return multiply(multiply(transformations(-angleDeg).stress, planeStressQ(p)), transformations(angleDeg).strain);
}
export function referenceABD(p: ElasticInputs, plies: { angleDeg: number; thicknessM: number }[]) {
  if (!plies.length) throw new Error("Specify at least one ply");
  plies.forEach(ply => { positive(ply.thicknessM); finite(ply.angleDeg); });
  const h = plies.reduce((sum, ply) => sum + ply.thicknessM, 0);
  finite(h);
  const blank = (): Matrix3 => [[0,0,0], [0,0,0], [0,0,0]];
  const A = blank(), B = blank(), D = blank();
  let bottom = -h / 2;
  for (const ply of plies) {
    const top = bottom + ply.thicknessM;
    const q = rotatedQ(p, ply.angleDeg);
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
      A[i][j] += q[i][j] * (top - bottom);
      B[i][j] += q[i][j] * (top**2 - bottom**2) / 2;
      D[i][j] += q[i][j] * (top**3 - bottom**3) / 3;
    }
    bottom = top;
  }
  return { A, B, D, h };
}
