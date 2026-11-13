import assert from "node:assert/strict";
import test from "node:test";
import { formatNumber, inProse, MINUS, superscript } from "../lib/number-format";
import { printed } from "../lib/studio-colors";
import { shown } from "../components/studio/laminate-results";
import { formatted, shortened } from "../components/abd-matrix";

test("one rule: four significant figures, plain from 0.001 up to a million, × 10ⁿ outside, the minus sign (ADR-0091 amendment 1)", () => {
  assert.equal(formatNumber(3.22), "3.220"); // a column keeps its zeros: 3.220 beside 3.474
  assert.equal(formatNumber(3.22, { zeros: false }), "3.22"); // a value in a sentence does not
  assert.equal(formatNumber(347449.98), "347400"); // plain below a million, four figures, never "3.474e+5"
  assert.equal(formatNumber(100000), "100000");
  assert.equal(formatNumber(1719), "1719");
  assert.equal(formatNumber(-497), `${MINUS}497.0`);
  assert.equal(formatNumber(0.2892), "0.2892");
  assert.equal(formatNumber(0.001), "0.001000");
  assert.equal(formatNumber(1.2346e-5), "1.235 × 10⁻⁵");
  assert.equal(formatNumber(-1.863e-15), `${MINUS}1.863 × 10⁻¹⁵`);
  assert.equal(formatNumber(63489172.24), "6.349 × 10⁷");
  assert.equal(formatNumber(1e6, { zeros: false }), "1 × 10⁶");
  assert.equal(formatNumber(999999.7), "1.000 × 10⁶"); // a value that rounds to a million is printed with its exponent
  assert.equal(formatNumber(0), "0");
  assert.equal(formatNumber(Number.NaN), "–");
  assert.equal(superscript(-12), "⁻¹²");
});

test("the page's formatters share the rule: the workspace's tables, the calculator's matrices and the readouts", () => {
  for (const value of [3.22, 347449.98, -0.000012345, 63489172.24, 22.56]) {
    assert.equal(shown(value), formatNumber(value), String(value));
    assert.equal(formatted(value), formatNumber(value), String(value));
    assert.equal(printed(value), formatNumber(value, { zeros: false }), String(value));
  }
  assert.equal(shown(null), "unbounded"); // a ratio no load reaches
  assert.equal(shown("x"), "–");
  // the home page's small tables: the same rule at three figures, never "9.88e+7", kept on one line by no-break spaces
  assert.equal(shortened(98_800_000), "9.88 × 10⁷");
  assert.equal(shortened(98_800_000).replace(/\s/g, " "), formatNumber(98_800_000, { figures: 3, zeros: false }));
  assert.equal(shortened(0.5367), "0.537");
  assert.equal(shortened(-4.2e-10), `${MINUS}4.2 × 10⁻¹⁰`);
  assert.equal(shortened(0), "0");
});

test("a sentence from the API reads its numbers in the page's form, its digits and names untouched", () => {
  // an exponent below a million, as sentences written before the rule have it, reads in plain digits, as the Summary beside it does
  assert.equal(inProse("By Tsai-Wu, ply 4 (90°) fails first when every load reaches 3.207 times its value: Nx = 3.207e+05 N/m."),
    "By Tsai-Wu, ply 4 (90°) fails first when every load reaches 3.207 times its value: Nx = 320700 N/m.");
  assert.equal(inProse("the top grip carries 1.622e+04 N, in tension."), "the top grip carries 16220 N, in tension.");
  assert.equal(inProse("Under Nx = 1e+05 N/m"), "Under Nx = 100000 N/m");
  assert.equal(inProse("Nx = 1.23456e+05 N/m"), "Nx = 123456 N/m"); // the digits the sentence wrote, none rounded away
  assert.equal(inProse("Nx = -3.474e+05 N/m"), `Nx = ${MINUS}347400 N/m`);
  assert.equal(inProse("eps_y = -497 microstrain (it shortens along y)"), `eps_y = ${MINUS}497 microstrain (it shortens along y)`);
  assert.equal(inProse("Ex = 1.5e+06 psi, alpha1 = -9e-07 /degC"), `Ex = 1.5 × 10⁶ psi, alpha1 = ${MINUS}9 × 10⁻⁷ /degC`);
  assert.equal(inProse("The stack [0/45/-45/90/90/-45/45/0] of 8 plies"), "The stack [0/45/-45/90/90/-45/45/0] of 8 plies"); // a layup as written
  assert.equal(inProse("element Coupon-1.1068 in ply 3 (-45°)"), `element Coupon-1.1068 in ply 3 (${MINUS}45°)`);
  assert.equal(inProse("Tsai-Hill R = 3.434"), "Tsai-Hill R = 3.434");
});
