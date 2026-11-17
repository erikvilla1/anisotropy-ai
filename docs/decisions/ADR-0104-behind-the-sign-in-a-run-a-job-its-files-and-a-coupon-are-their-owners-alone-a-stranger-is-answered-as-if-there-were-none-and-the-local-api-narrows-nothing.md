# ADR-0104: Behind the sign-in a run, a job, its files and a coupon are their owner's alone; a stranger is answered as if there were none, and the local API narrows nothing

- Status: Proposed
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 (chose "Only the owner" on the card "Choose who can see a user's runs, files and coupons on the site", over "Owner, and you can read" and "Owner and their company"); how it is built is the draft's proposal and not yet confirmed | Drafted by: Claude Code
- Related: [ADR-0011](ADR-0011-local-laminate-api.md); [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md); [ADR-0050](ADR-0050-coupon-jobs-through-the-api-run-the-tool-in-the-background-one-at-a-time.md); [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md); [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md); [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md); [ADR-0094](ADR-0094-models-move-to-and-from-abaqus-through-a-connector-under-the-users-own-abaqus-and-one-versioned-bundle-compared-privately.md); `api/src/anisotropy_api/main.py`, `api/src/anisotropy_api/records.py`, `api/src/anisotropy_api/coupon_jobs.py`, `api/tests/test_private_records.py`
- Area: api, data, hosting

## Context

- Every request to the hosted API comes through Cloudflare Access, which verifies the person's email; the API keeps it on each run record and each job (ADR-0056, ADR-0026 amendment 1).
- Projects, uploads from Abaqus and upload tokens are already their owner's: another person is answered 404 (ADR-0062 part 6, ADR-0094 part 6).
- Runs, jobs, a job's files and the coupons were not. Any signed-in person could list every run and every job (`GET /v1/runs`, `GET /v1/coupon-jobs`), open any job, its package and its files by id, ask for its explanation, list every coupon on the machine, read a coupon's rows back and run it again by name. An upload could be put beside any job named by its id.
- A job's id is a random UUID, but the two lists gave every id away.
- The page offered every coupon on the machine to reopen, whoever ran it. It shows no list of runs or jobs; those were open in the API alone. Customers have not been invited yet.
- The local API has no sign-in and one user (ADR-0011).
- A coupon's folder is named by its designation, which is derived from the material, the test and the layup (ADR-0038 amendment 1). Two people who run the same three share one folder, and its spec holds the rows of whoever ran it last.

## Options considered

Who may read a record:

1. Only the owner, the signed-in email that made it. No one reads another's work, the founders included. Support for a customer's run then needs the customer to send it, or the database.
2. The owner, and the founders may read. As uploads are today (ADR-0094 part 6). The founders can help with any run; a customer's data is then readable by us through the site.
3. The owner and the people of their company. Needs companies, membership and an invitation flow, none of which exist.

What a stranger is told:

4. 404 in the same words as for an id there is none of. Nothing is confirmed to exist.
5. 403. Says the record exists, which is itself information about another person's work.

Where the rule applies:

6. Behind Access only; with no sign-in in front of the API nothing is narrowed. The local API keeps working as it does.
7. Everywhere, by the actor header when there is no email. The actor is a client's name, not an identity, and a browser's file link carries none; it would break the local downloads and protect nothing.

A request behind Access with no email (a service token):

8. It sees the records made with no email, and no person's.
9. It sees everything. A service token would then be a way around the rule.

The coupons, whose folders are shared by name:

10. A coupon is offered to a person when their jobs have run it. Two people who ran the same material, test and layup would each read back the rows of whoever ran last.
11. A coupon is offered to a person only when their jobs alone have run it. A name two people have run is offered to neither; each still has their projects, their jobs and their files.
12. One folder of coupons per owner. Closes the shared names as well; changes the tools' root, the keys in the object store, the restore at startup and the coupons already there, and needs a record of its own.

## Decision

Options 1, 4, 6, 8 and 11.

- Behind Cloudflare Access a run record, a job, a job's package, files and explanation are readable only by the signed-in email that made them. The lists (`GET /v1/runs`, `GET /v1/coupon-jobs`) hold the requester's own, narrowed in the query so the limit counts their own.
- Anyone else is answered 404 in the words used for an id there is none of.
- A request with no email behind Access (a service token) sees the records made with no email.
- With no sign-in in front of the API nothing is narrowed.
- The list of coupons, a coupon's rows and a job started from a coupon's name are for the person whose jobs alone have run that coupon; anyone else is answered 404 in one wording, whether the name exists or not.
- A run named by its id is put beside an upload only when it is the uploader's own.
- The email is compared as Access states it, to the letter, as projects compare it.
- Uploads stay as ADR-0094 part 6 left them: their owner's, and readable by the founders.

## As built (2026-11-16)

- `api/src/anisotropy_api/main.py`: `_owner(request)` (the email behind Access, `EVERYONE` with Access off), `_theirs`, `_known_job(request, jobs, job_id)` for the job, its package, its files and its explanation, `_their_coupon` for a coupon's rows and a job started from its name, the owner passed to `list_runs` and `CouponJobs.listed`, the owner's check in `run_detail` and in `_our_run`.
- `api/src/anisotropy_api/records.py`: `EVERYONE`, `_owned`, the `user_email` of `list_runs` and `list_jobs`, `coupon_owners`, `coupons_of`.
- `api/src/anisotropy_api/coupon_jobs.py`: `listed(user_email)`, `coupons_of(user_email)` over this process's jobs and the jobs table.
- No migration: `runs.user_email` and `jobs.user_email` exist. No change to the page or the Worker.
- Difference from the plan: none.

## Why (evidence)

- The founder's choice on 2026-11-16, quoted above. The choice of options 4, 6, 8 and 11 is the draft's.
- `cd api && TEST_DATABASE_URL=... uv run pytest -q tests/test_private_records.py`: 10 passed on 2026-11-16, each scenario once with the jobs table and once with this process's jobs alone. They cover: a second signed-in person, a service token and the owner's email in other letter case each list no job and get 404, in the words of an unknown id, for the job, its package, its two file routes and its explanation; each person lists their own jobs and runs; a filter on the run list widens nothing; a coupon is listed, read back and run again by its owner, is 404 to anyone else in the words of a name there is none of, and is offered to neither once a second person has run it; the local API shows every record; the limit of a list counts the owner's rows.
- With `_theirs` made to answer yes, 6 of those 10 fail (the four that pass are the coupon scenario in both setups, which does not go through it, the local API's and the queries').
- `api/tests/test_abaqus_uploads.py::test_behind_access_an_upload_stands_beside_its_owners_runs_alone`: passed; another person's run named by id is "there is no coupon job", at the upload and when asked later.
- `api/tests/test_access.py::test_the_email_is_on_the_run_record` asserted that a signed-in person could read a service token's run; it now asserts the service token reads it and the person gets 404.
- The whole API suite on 2026-11-16, in a cloud container with a test database: `uv run pytest -q`, 637 passed and 1 skipped. `npm run typecheck`: clean.
- UNVERIFIED: not tried on the hosted site with two real sign-ins. How many rows of the hosted database carry no email is not counted; those rows are now readable by no signed-in person.

## Consequences

- One customer cannot list, open, download or ask about another's runs and files, nor reopen their coupon.
- The founders cannot read a customer's run through the site. Usage and support go through the database, or the customer sends the package.
- A run or job recorded with no email is hidden from every signed-in person.
- A coupon two people have run under one name drops out of both people's list to reopen; their projects keep their rows.
- What the shared coupon names still show: the setup check says whether a coupon of the derived name exists and how many attempts it has, the layup's number in the name counts other people's layups, and a result's attempt number counts other people's attempts. No row, file or name of another person is shown.
- Every new route that reads a run, a job or a coupon must go through `_known_job`, `_their_coupon` or `_owner`.

## Not in this record

- One folder of coupons per owner (option 12), which removes the shared names.
- Companies and sharing between colleagues (option 3).
- A page that lists a person's past runs.
- A way for a founder to read a customer's run on request, with the customer's consent.
- Deleting a person's records on request.

## How we will know it was wrong

- A signed-in person reads, lists or downloads anything of another's through any route.
- A customer loses work they could reach before: a run, a file or a coupon that is theirs is answered 404.
- Support needs a customer's run more than once a month and the database is too slow a way to it: then option 2, or reading on request with consent.
- Two customers run the same material, test and layup often enough that the list to reopen is empty for them: then option 12.
