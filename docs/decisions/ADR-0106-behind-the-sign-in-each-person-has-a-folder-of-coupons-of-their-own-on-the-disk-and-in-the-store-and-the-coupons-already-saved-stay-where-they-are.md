# ADR-0106: Behind the sign-in each person has a folder of coupons of their own, on the disk and in the store, and the coupons already saved stay where they are

- Status: Proposed
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 (the plan's "one coupon folder per person", kept in the order after "do MCP last"; and chose "Start fresh, keep the old files" on the card "Choose what happens to coupons already saved on the live site", over "Move each to its one owner" and "Show me the plan first"); how it is built is the draft's proposal and not yet confirmed | Drafted by: Claude Code
- Related: [ADR-0104](ADR-0104-behind-the-sign-in-a-run-a-job-its-files-and-a-coupon-are-their-owners-alone-a-stranger-is-answered-as-if-there-were-none-and-the-local-api-narrows-nothing.md) (its option 12, left for a record of its own); [ADR-0003](ADR-0003-reject-invalid-input.md); [ADR-0038](ADR-0038-coupon-identity-card-and-designation.md); [ADR-0040](ADR-0040-one-folder-per-problem-named-for-it.md); [ADR-0050](ADR-0050-coupon-jobs-through-the-api-run-the-tool-in-the-background-one-at-a-time.md); [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md); [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md); [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md); `fea/src/anisotropy_fea/paths.py`, `fea/tools/studio_tool.py`, `api/src/anisotropy_api/storage.py`, `api/src/anisotropy_api/coupon_jobs.py`, `api/src/anisotropy_api/live.py`, `api/src/anisotropy_api/main.py`
- Area: api, fea, data, hosting

## Context

- A coupon's folder is named by its designation, which is derived from the material, the test and the layup (ADR-0038 amendment 1). Until now there was one folder of coupons for everyone: `.local/fea/<coupon>/` on the disk and `coupons/<coupon>/` in the object store.
- ADR-0104 made a coupon its owner's by the jobs table: offered only to the person whose jobs alone have run it. It left three things the shared folder still showed, and named them: two people who run the same material, test and layup write one folder, and the name is then offered to neither; the setup check says whether a coupon of the derived name exists and how many attempts it has, counting other people's; the layup's number in a name and a result's attempt number count other people's coupons and attempts.
- A material or layup code means one thing among "the coupons on this machine" (`intake.designation_for`). With one folder, a code one customer chose was refused to the next with other constants.
- The fea package takes every location from `paths.LOCAL`, fixed at `.local/fea`. `studio_tool.py` has `--root`; `run_coupon.py` and the scripts it runs have none.
- One warm `studio_tool.py serve` worker answers the live previews of many people (ADR-0086).
- With the job queue the API's container and each solver container keep their coupons level with the store (ADR-0056 amendments 3 and 9).
- No customer has been invited to the hosted site yet. The coupons in the live store were made by the founder and the team.

## Options considered

Where a person's coupons are kept:

1. One folder for everyone, the owner worked out from the jobs table (ADR-0104 option 11, as it stood). No change to the tools or the store; the three leaks above stay.
2. One folder of coupons per signed-in person, on the disk and in the store. The tools read and write that folder alone, so names, codes, attempts and rows are settled among one person's coupons.
3. The owner in the coupon's name (a prefix or suffix on the designation). The name is printed in every deck, document and file name; it would carry a customer's identity into files they send on, and change the designation rules of ADR-0038.

How a folder is named:

4. A key made from the signed-in email: the first 32 hex digits of its SHA-256. No lookup table, the same in every container, and no path, object key or log line holds an address.
5. The email itself. Characters a path or a key does not take, and a customer's address in every key and listing.
6. A random id per person kept in a new table. Hides more than a digest of a guessable address does, at the cost of a migration and a database read wherever a folder is named; the solver would need it before it could fetch.

How a tool is told the folder:

7. The environment (`ANISOTROPY_COUPONS_ROOT`), read once where `paths.LOCAL` is set. A run, the scripts it starts and every function that takes a location from `paths` follow it with no other change.
8. A `--root` option on every tool and script. Each of the five scripts a run starts, and every function between them, would have to pass it on; one missed call writes into the shared folder.
9. For the warm worker, the folder in each request. It cannot be the worker's environment: one worker answers many people.

The coupons already in the store:

10. Left where they are, under `coupons/`. Each person's list to reopen starts empty; their projects, past runs and those runs' files still open. Nothing in the live store is changed or deleted.
11. Moved once to their one owner, by a script the founder runs against the live store. Keeps the reopen list for the few coupons with one owner; a one-time change to production data.

A request with no email behind the sign-in, and the local API:

12. The shared folder, as before, with ADR-0104's rule for a service token.
13. A folder for "no one" as well. Nothing gains from it, and the founder's own machine would lose its coupons from the list.

## Decision

Options 2, 4, 7, 9, 10 and 12.

- Behind Cloudflare Access a signed-in person's coupons are kept in a folder of their own: `.local/fea-owners/<key>/<coupon>/` on the disk and `owners/<key>/coupons/<coupon>/...` in the store, laid out inside as `.local/fea/<coupon>/` and `coupons/<coupon>/...` are.
- `<key>` is the first 32 hex digits of the SHA-256 of the email as Access states it, to the letter, as ADR-0104 compares it. It is a name, not a secret: who may read a folder is decided by the sign-in.
- A job, the setup check, the live preview, the list of coupons and a coupon's rows read and write the folder of the person who asked. The list to reopen is that folder's coupons; a job started from a coupon's name needs the coupon in it; anything else is 404 in ADR-0104's words.
- The API starts every tool with the folder in `ANISOTROPY_COUPONS_ROOT`; `paths.LOCAL` is that folder when the variable is set, `.local/fea` otherwise. A value that is not an absolute path is refused (ADR-0003). A request to the warm worker names the folder itself.
- A solver container fetches the job's owner's coupons only, and removes what an earlier job of another person left on its disk.
- The coupons already saved stay under `coupons/`, untouched. A signed-in person's list starts empty.
- A request with no email (a service token) and the API with no sign-in in front of it keep the shared folder and ADR-0104's rules for it.

## As built (2026-11-16)

- `fea/src/anisotropy_fea/paths.py`: `COUPONS_ROOT`, `coupons_root()`, `LOCAL` from it.
- `fea/tools/studio_tool.py`: `serve` takes a request's `root` (`request_root`); `--root` defaults to the environment's folder.
- `api/src/anisotropy_api/storage.py`: `owner_key`, `coupons_prefix`, an `owner` on `file_key`, `package_key`, `folder_key`, `store_file`, `store_job`, `store_folder`, `restore` and `sync`; `restore_owners`. A coupon named `.` or `..` in a key is skipped, as a path part was.
- `api/src/anisotropy_api/coupon_jobs.py`: `OWNERS_FEA`, `CouponJobs.owners_root`, `root_of`, `has_coupon`, `_tool_env`; `refresh`, `check`, `list_coupons` and `coupon_values` take the email; a job's run, its files, its gate and its solver's sync use its owner's folder and prefix.
- `api/src/anisotropy_api/live.py`: `LiveSolver.solve(root=)`, per request to a warm worker and `--root` to a fresh tool.
- `api/src/anisotropy_api/main.py`: `_their_coupon` asks the person's folder; the list, the values, the check and the live preview pass the email; at startup a container that runs the jobs itself restores every person's coupons, and one behind the job queue brings a person's level when they ask.
- No migration, no change to the page or the Worker.
- Differences from the plan: none was written down before the build. The unique index that lets one running job hold a coupon is still by the coupon's name alone (see Consequences).

## Why (evidence)

- The founder's choices on 2026-11-16, quoted above. Options 2, 4, 7, 9 and 12 are the draft's.
- `api/tests/test_private_records.py` (16 passed on 2026-11-16, each scenario with the jobs table and with this process's jobs alone): a person's coupon is listed, read back and run again by them and is 404 to a second person and to a service token; a second person's coupon of the same name is another coupon, each reads back their own rows and runs their own again; the disk holds one folder per person under the key and nothing in the shared folder; the same address in other letter case is another owner, as for the records; a service token's job keeps the shared folder; the setup check and the live preview, by a warm worker and by a fresh tool, are started with the asker's folder.
- `api/tests/test_job_queue.py::test_a_signed_in_persons_job_keeps_its_coupon_in_their_own_folder_and_under_their_own_prefix`: through the queue, two people's jobs and one with no email on one coupon name each number their own attempts (02, 02, 02; a person's second run 03, fetched back from the store after another person's job cleared the solver's disk); the objects lie under `owners/<key>/coupons/` and `coupons/`; no key holds an address; the API's container reads each person's coupons into their own folder when they ask.
- `api/tests/test_storage.py`: the key and the prefixes; a prefix that is not a key is refused; two people's folders are stored, synced, pruned and restored apart from each other and from `coupons/`; a key that would leave its folder is skipped.
- `fea/tests/test_studio_tool.py`: with the variable set, `paths.LOCAL`, `paths.ours()` and `paths.model_dirs()` are that folder's in a new process and `studio_tool.py coupons` lists its coupons; a relative value is refused; `run_coupon.py` started by a coupon's name looks for it in the environment's folder and in no other; one warm worker answers three requests with three folders, and the coupon exists in its owner's alone.
- With the real studio tool through `CouponJobs` and `LiveSolver` in a cloud container (a script, not a test): a coupon made in one person's folder is listed, checked as existing with 1 attempt and read back for that person; for a second person and for no one the list is empty and the same rows check as a new coupon, by a warm worker and by a fresh tool.
- The whole API suite: `cd api && TEST_DATABASE_URL=... uv run pytest -q`, 655 passed and 1 skipped on 2026-11-16, in a cloud container with a test database. The fea suite: `cd fea && uv run pytest -q -ra tests ../engine/tests`, 1615 passed, 43 skipped, 3 failed and 1 error; the four are the tests that need Gmsh, which this container lacks, and fail the same way on main (CI has Gmsh).
- UNVERIFIED: no full run (CalculiX, the mesh study, the package) was made under a person's folder; this container has no CalculiX, and the runner's own tests set `paths.LOCAL` directly. Not tried on the hosted site, with the job queue's real containers, R2 or two real sign-ins. How long a person's first request waits for their folder to be listed from R2 is not measured.

## Consequences

- Two customers who run the same material, test and layup each keep their own coupon, rows, attempts and packages. The check's "this coupon exists", the attempt number and the layup's number in a name count a person's own work only.
- A material or layup code is one person's to give: another customer's codes neither block nor name theirs.
- On the hosted site every signed-in person's list to reopen starts empty, the founder's included. The old coupons stay in the store under `coupons/`; past runs, their files and the projects open as before; a project run again makes a new coupon in the person's own folder, numbered from attempt 01.
- The founders cannot see a customer's coupons through the site, as ADR-0104 decided for runs.
- A person whose email changes, or is stated in other letter case, gets an empty folder; the old one stays in the store under its key.
- The key is a digest of an address, not a secret: someone who can list the bucket and guesses an address can tell which folder is whose. Whoever can list the bucket can read it all anyway.
- One running job still holds a coupon's name for everyone (the unique index of migration 0008): two people's jobs on coupons of one name run one after the other, and the second is told another job is solving a coupon of that name.
- The API's container keeps a folder per person who has asked; a solver's disk holds one person's coupons at a time.
- The tools depend on one more environment variable. A tool started by hand without it uses `.local/fea`, as before.

## Not in this record

- Moving the old coupons to their owners (option 11).
- The claim of a coupon per owner, which needs a migration of the unique index.
- A shared folder for the people of one company (ADR-0104 option 3).
- Deleting a person's folder on request.
- The page: it shows the list it is given and needed no change.

## How we will know it was wrong

- A signed-in person sees, in a list, a check, a name, an attempt number or a file, anything that comes from another person's coupon.
- A job writes a coupon into `.local/fea` or under `coupons/` although its owner has an email.
- A customer asks for a coupon they made before this change often enough that starting fresh costs them work: then option 11 for those coupons.
- Two customers wait on each other's jobs because their coupons share a name: then the claim per owner.
- A person's first request after a container starts waits noticeably on the listing of their folder: then their coupons are restored at startup, or the listing is kept.
