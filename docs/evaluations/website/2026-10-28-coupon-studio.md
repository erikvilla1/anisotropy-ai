# The coupon studio page (2026-10-28)

Part 2 of the plan behind ADR-0051, on `feat/studio-page`, stacked on the foundations of part 1. What was built is in the record's
"As built" section and the card `docs/components/studio.md`; this note holds the runs and their output.

## Unit tests and the build

| Check | Command | Result |
| --- | --- | --- |
| website unit tests | `npm test` | 96 passed, 0 failed (71 before, 25 new in `tests/studio-{form,geometry,colors,fields,api}.test.ts`) |
| types | `npm run typecheck` | `tsc --noEmit` clean |
| the static export | `NEXT_PUBLIC_ANISOTROPY_API_URL=http://127.0.0.1:8000 npm run build` | 13 routes prerendered, `/studio` and `/studio/view` among them |

What the unit tests hold: the form is the package's exported definition (one row per field, the ply and hole rows, the library); the
values object parses numbers and leaves blanks out without judging; a coupon read back fills the form; a checklist's failing rows land
on their fields; the plate is a closed surface with four vertices per element face, its top triangles counterclockwise and its bottom
reversed; the page's own node means equal the package's display averages to 1e-9 on the fixture; the colour scale is diverging only
for a signed field and grey at zero; the field picker returns the package's arrays per element or per node; the readout of the critical
element names its ply, ratio and mode; the API client sends the studio's actor and reads every answer's shape.

## The browser test with the API played from the fixtures

`npm run test:studio` (Playwright, Edge channel on this machine, Chromium on CI), the API intercepted and answered from
`tests/fixtures/studio/` (the public IM7/8552 example, 250 elements, written by `fea/tools/studio_tool.py fixtures`): 3 passed in 28 s.

- The studio loads the example, checks the setup (the values sent hold `length` 250, `ply_1` 45, `library` im7-8552 and the form's
  version), shows twelve passed items and the preview, solves, shows the job's stages, fills the viewer as soon as the fields are
  listed (the legend reads "Failure index 1/R, worst ply"), prints the reaction, the Tsai-Hill factor 1.013 and the sentence "does not
  exceed the Tsai-Hill criterion", ends with the package and the PrePoMax files among the links and nine stages done, switches the
  field to S22 of ply 3 as element values, and reads the critical element from the first-ply-failure table. No page error.
- A blank Length blocks the setup: the row is marked invalid, the geometry item reads "needs input", the solve stays off.
- A coupon reopens into the form; the viewer window reads a job from its address and says so when there is none.

Screenshot: `.local/website/screenshots/studio-results.png` (looked at: the contour on the plate, the legend, the readout, the summary
table, the explanation, the file list).

## The live run on the founder's machine

`STUDIO_LIVE=1 npm run test:studio-live`: the real API (recording off), the real fea tools, CalculiX 2.22 and Tectonic. 1 passed in 1.1 min.
From the page: the example loaded, the material code IM7 and no layup code, the setup check answered ready, Solve started the job,
the fields appeared after our engine's step, and the job ended done with "57 of 57 recorded values agree with CalculiX; our reaction
+0.35 % from CalculiX's". It made the coupon `.local/fea/IM7-UNT-L2/` (the next free layup code for IM7 on this machine): the values
file filed in `team/2026-10-28/`, the case page with rows 01 and 02, attempt 02 with `run/kernel`, `run/calculix` and `run/studio`, the
record and the package `documents/2026-10-28_IM7-UNT-L2/`. The fields: 1500 elements (2 mm), reaction 16211.2 N, first-ply failure by
Tsai-Hill at 0.8961 of the pull and by maximum stress at 0.9151, both at the edge of a gripped tab, the same numbers the form's
end-to-end run of 2026-10-25 gave. Screenshot: `.local/website/screenshots/studio-live.png`. The coupon was then removed and the case
pages regenerated, as the earlier demonstration coupon was (ADR-0046's evidence); the example stays in `.local/fea/forms/example/`.

## Not done here

- The founder's own use of the page (the walk through the plan's verification list) is theirs to do; every step of it ran in the two
  tests above.
- WebGL in CI's headless Chromium: UNVERIFIED until the `studio-browser` job runs (GitHub Actions did not start on 2026-10-28 for a
  billing reason, see part 1's note); the page detects a missing context and says so, and the test asserts DOM state only.
- A timing of the check on an open-hole (Gmsh) coupon from the page.
