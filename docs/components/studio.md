# Component card: the coupon studio | version 0.1 | updated 2026-10-28

## Purpose and intended use

A page of the website, `/studio`, where an engineer states a coupon test, checks its setup, solves it and reads the result in a 3D view, without installing anything (ADR-0051). It replaces the terminal for the four in-plane coupon tests (unnotched tension and compression, open-hole tension, in-plane shear). The viewer opens in a second window by the job's link, `/studio/view?job=<id>`.

## What it does and does not compute

Nothing. Every number the page shows is written by the fea package: the setup checklist and the preview (`POST /v1/coupon-jobs/check`), the fields with their display averages and the summary (`fields.json`), and the template explanation (`explanation.json`), read as files of the job (ADR-0050 amendment 1). The page parses text into the values object, picks arrays, maps values to colours and draws (ADR-0001). The form's rows are the package's own definition, `lib/coupon-form-definition.json`, exported by `fea/tools/export_form_definition.py` and checked against the package by `fea/tests/test_studio_tool.py`.

## Inputs / outputs

Input: the rows of the coupon input form (ADR-0046), typed, picked from the library, loaded from the public example, or read back from a coupon on the machine (`GET /v1/coupons/{name}/values`). Output: the checklist (twelve items, each passed, warned, failed, missing or pending, with the rows it concerns), the preview of the model (the mesh with the held tab framed in violet and the pulled tab framed in amber with an arrow), the job's stages, the fields (displacement, strains, section forces, every ply's stresses in material axes and its von Mises stress, the failure index and strength ratio by criterion; element values or display averages, deformed or not), the summary (reaction, largest displacement, largest ply stresses, first-ply failure by criterion with the critical element framed in red), the explanation, and links to every file of the job: the package zip, the PDF, the decks, the `.vtu`, the record, the JSON files.

## Dependencies and connections

Next.js (static export), React Three Fiber and drei on three.js (MIT), loaded only in the browser (`next/dynamic` with `ssr: false` inside a client component, as the installed Next.js docs require). The API of ADR-0050 with amendment 1: the check, the job with its stage and files, the coupon listing. The actor is `studio`. Drawing code: `lib/studio-geometry.ts` (the plate with four vertices per element face, its deformed shape, the outline frames), `lib/studio-colors.ts` (one hue for a magnitude, two hues around a neutral grey for a signed field, fixed slots for ply angles), `lib/studio-fields.ts` (which array a field shows), `lib/studio-form.ts` and `lib/studio-api.ts`.

## Evaluation

[The studio page](../evaluations/website/2026-10-28-coupon-studio.md): the unit tests of the drawing and form code, the browser test with the API played from the public fixtures, and the live run on the founder's machine.

## Out of scope and limits

The founder's machine only (ADR-0027 item 4 brings authentication later); one job at a time (ADR-0050). In-plane coupons only; bending and the general `plate` kind are parts 4 and 5 of the plan. The 3D view needs WebGL; without it the page says so and shows the numbers, the checklist, the summary and the explanation. A job's status is lost when the API stops. The colours carry no number: the legend's ticks and the readout do.

## Owner

Founder / engineering.
