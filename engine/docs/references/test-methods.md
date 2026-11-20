# Test methods behind a strength

Which test gives each strength a wing check uses, what the test does, and where its number enters the wing (ADR-0127). The material record names the method of every value it holds, so an answer reads the method of a given strength from the record; this page explains the method.

Status: a draft of 2026-11-20, not yet reviewed by the founder. Written in our own words. ASTM standards are licensed references (ADR-0018 amendment 1): this page gives a standard's number and our own description of it, never its text, figures or tables.

A material's strengths come from a qualification program: flat panels made by a fixed process from several batches of material, cut into specimens, conditioned, and tested by a standard method in each environment. The statistics that turn the results into an allowable are in the page on allowables.

## Tension along and across the fibres (ASTM D3039/D3039M)

<!-- also: tension test, tensile test, tensile strength, F1t, F2t, Xt, Yt, longitudinal tension, transverse tension, tensile modulus, E1, E2, Poisson ratio, straight-sided coupon, tabs, D3039 -->

A straight-sided flat strip with bonded end tabs is pulled until it breaks, with the strain measured in the middle. A strip of 0° plies gives the strength and modulus along the fibres, F1t and E1, and the major Poisson ratio; a strip of 90° plies gives them across the fibres, F2t and E2. The same method tests whole laminates. It is the test our coupon analyses model.

In the wing, F1t judges the 0° plies of the lower skin and caps, stretched along the span when the wing bends up; F2t judges any ply stretched across its fibres, such as a 90° ply in the same skin.

Sources: ASTM D3039/D3039M (number only); NCAMP data report CAM-RP-2009-015 Rev B names it for the IM7/8552 tension values, as the material record does.

## Compression along the fibres

<!-- also: compression test, compressive strength, longitudinal compression, F1c, Xc, CLC, combined loading compression, D6641, D3410, D695, cross-ply, back-out, backout factor, UNC0 -->

Compression along the fibres is the hardest strength to measure. A unidirectional strip crushes at its ends or buckles as a column before its fibres fail in the middle. Two fixtures are common. ASTM D6641/D6641M loads a short unsupported gauge length through both the ends and the clamped faces (combined loading compression). ASTM D3410/D3410M loads it only through the faces, in shear.

NCAMP does not test 0° tape in compression directly. It tests a cross-ply laminate with one third of its plies at 0° and derives the 0° ply's strength with a back-out factor worked from the plies' moduli and the major Poisson ratio. The derived strength is a property of the ply inside a laminate, which is how the wing uses it.

In the wing, F1c judges the 0° plies of the upper skin and caps when the wing bends up, and of the lower skin when it bends down. On the example wing it governs.

Sources: ASTM D6641/D6641M and ASTM D3410/D3410M (numbers only); NCAMP statistical report NCP-RP-2009-028 Rev B, section 2.5, p. 32 (the back-out formula, after CMH-17-1G, equation 2.4.2.1(b)); which fixture the cross-ply test used is in the data report CAM-RP-2009-015 Rev B, not read here.

## Compression across the fibres (ASTM D6641/D6641M)

<!-- also: transverse compression, F2c, Yc, compressive strength across the fibres, 90 degree compression -->

A strip of 90° plies is crushed in the combined loading fixture. The matrix carries the load, so the strength is several times the strength across the fibres in tension, but far below the strength along them.

In the wing, F2c judges a ply pressed across its fibres, as a 90° ply of the upper skin is by the Poisson effect of the spanwise compression.

Sources: ASTM D6641/D6641M (number only); NCAMP data report CAM-RP-2009-015 Rev B names it for the IM7/8552 value, as the material record does.

## In-plane shear (ASTM D3518/D3518M; ASTM D5379/D5379M)

<!-- also: shear test, shear strength, in-plane shear, F6, F12, S12, S, tau12, shear modulus, G12, plus minus 45 tension, ±45 tension, V-notched beam, Iosipescu, 5 % strain, 0.2 % offset, D3518, D5379 -->

The common shear test pulls a ±45° laminate. Each ply then carries shear in its own axes equal to half the stress in the strip, and the shear strain is the strain along the strip minus the strain across it. The response is far from straight: the shear stress keeps rising slowly to large strains. The method therefore stops the strength at 5 % shear strain if the strip has not failed before. A second value, at 0.2 % offset from the straight start of the curve, marks where the response leaves the straight line; it is much lower, and some designers use it where a ply must not yield.

The V-notched beam, ASTM D5379/D5379M, shears a notched bar directly between its notches and gives the same properties by another route.

In the wing, F6 judges the shear in every ply, most of all in the ±45° plies of the webs and in the skins under torsion. The wing uses the strength at 5 % strain; the record keeps the 0.2 % offset value beside it (ADR-0126).

Sources: ASTM D3518/D3518M and ASTM D5379/D5379M (numbers only); NCAMP statistical report NCP-RP-2009-028 Rev B, Table 1-2 (p. 11) names the two shear strengths.

## Short-beam strength (ASTM D2344/D2344M)

<!-- also: short beam, short beam shear, SBS, interlaminar shear, ILSS, three point bend, three-point bending, apparent interlaminar shear strength -->

A short, thick bar is bent between close supports, so it fails by shear between plies before it fails in bending. The result is an apparent interlaminar shear strength, useful to compare materials and processes and to screen the effect of moisture and heat. It is not a design value for the shear between plies, since the stress in the bar is not uniform.

The wing does not use it.

Sources: ASTM D2344/D2344M (number only); NCAMP statistical report NCP-RP-2009-028 Rev B, Table 3-1 (p. 35) lists it with the lamina strengths.

## Open-hole tension and compression (ASTM D5766/D5766M; ASTM D6484/D6484M)

<!-- also: open hole, OHT, OHC, notched strength, hole, fastener hole, notch, notch sensitivity, filled hole -->

A laminate strip with a hole in the middle is pulled or crushed. A laminate does not yield around a hole as a metal does, so the hole lowers its strength markedly; the strength of the laminate with the hole is measured instead of computed from the plies. Results depend on the layup, so they are given for named laminates.

The wing does not check holes or fasteners yet. A wing with access holes or bolted joints would judge the laminate near them by these strengths.

Sources: ASTM D5766/D5766M and ASTM D6484/D6484M (numbers only); NCAMP statistical report NCP-RP-2009-028 Rev B lists open-hole results by layup.

## Bearing (ASTM D5961/D5961M)

<!-- also: bolt bearing, pin bearing, fastener bearing, bolted joint, joint, bearing strength -->

A bolt or pin in a hole presses on the laminate until the hole elongates or the laminate fails around it. It gives the bearing strength of a bolted joint for a named laminate and fastener.

The wing does not check joints yet.

Sources: ASTM D5961/D5961M (number only).

## Impact and compression after impact (ASTM D7136/D7136M; ASTM D7137/D7137M)

<!-- also: impact, drop weight, drop-weight impact, compression after impact, CAI, barely visible impact damage, BVID, damage tolerance, residual strength, dent -->

A plate is struck by a falling weight, the damage is recorded, and the same plate is then crushed in a fixture that keeps it from buckling. The damage, often little more than a dent on the surface with delaminations inside, lowers the compression strength markedly.

Airworthiness guidance asks that damage likely in manufacture and service, up to what the planned inspection can find, not lower the strength below ultimate load, shown by tests or by analysis supported by tests; in practice it is often met by limiting the design strains of a laminate. The wing does not check damage yet; its margins are those of undamaged structure.

Sources: ASTM D7136/D7136M and ASTM D7137/D7137M (numbers only); FAA AC 20-107B, paragraph 6.g (p. 7), on limiting design strains for impact damage, and paragraph 7.f (p. 10), on damage up to what the planned inspection can find.
