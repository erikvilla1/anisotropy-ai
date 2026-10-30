# The solver image

One Docker image holds the API and every program a coupon job needs: the engine, api and fea packages with their locked
environments, CalculiX, Gmsh and Tectonic with its TeX files already fetched (ADR-0056). It is plain Docker with nothing
platform-specific inside, so the same image runs on Cloudflare Containers, on Google Cloud Run, on a customer's servers
(ADR-0027) or on a laptop. Abaqus is never in it (ADR-0045).

## Build and run

From the repository root:

```bash
docker build --build-arg GIT_COMMIT=$(git rev-parse HEAD) -t anisotropy-solver .
docker run --rm -p 8080:8080 -e ANISOTROPY_RUN_RECORDS=off anisotropy-solver
curl http://127.0.0.1:8080/healthz        # {"status":"ok"}, without the database
```

With run records on, pass `DATABASE_URL` instead of the switch (ADR-0026); the API refuses to start without a reachable,
migrated database. `GIT_COMMIT` becomes `ANISOTROPY_GIT_COMMIT` inside the image: there is no `.git` there, so that is where
the run records' `git_commit` comes from.

## What is inside

| Piece | Where it comes from | Why |
| --- | --- | --- |
| Ubuntu 24.04 | `ubuntu:24.04` | the same CalculiX package as CI |
| CalculiX 2.21 | apt `calculix-ccx` | the reference solver (ADR-0030) |
| GL, GLU, X11 pieces, fontconfig, OpenMP | apt `libgl1 libglu1-mesa libgomp1 libfontconfig1 libxcursor1 libxfixes3 libxft2 libxinerama1 libxrender1` | what the Gmsh wheel links (`ldd libgmsh.so`); CI's runner has them, a bare image does not |
| uv 0.13.0 | `ghcr.io/astral-sh/uv` | the environments, from the three lockfiles |
| Python 3.12 | `uv python install` | one managed interpreter for the three environments |
| Tectonic 0.17.0 | its GitHub release, the static build | the PDF; the same release CI installs |
| `engine/.venv`, `api/.venv`, `fea/.venv` | `uv sync --locked` | the packages; fea with `--extra mesh` (Gmsh) and its dev group (matplotlib draws the figures) |
| Tectonic's cache | `docker/warm-tectonic.py` at build | every TeX package and font the coupon document uses: the script takes the public IM7/8552 coupon through `run_coupon.py` to its PDF once and removes the run, so a running container downloads nothing |

The API starts as `/app/api/.venv/bin/uvicorn anisotropy_api.main:app --host 0.0.0.0 --port 8080`, as the service user `app`.
A coupon job runs `uv run --project fea python fea/tools/run_coupon.py` as it does on a laptop (ADR-0050), with `UV_NO_SYNC=1`
so nothing is installed at run time. Its files go under `/app/.local/fea/<coupon>/`, which lives as long as the container does;
durable outputs are the next chunk of ADR-0056.

`.dockerignore` keeps out `.local/`, `node_modules/`, `out/`, the website, every virtual environment and every `.env` file.

## Check it

`docker/check-image.py` runs inside the container, with the network off, and takes the public IM7/8552 coupon (the studio's
values fixture, never a team coupon) through the API to its package with the PDF. It prints the job's time, the document and
fields sizes and the container's peak memory. The CI job `image` in `.github/workflows/tests.yml` does exactly this:

```bash
docker run -d --name api --network none -e ANISOTROPY_RUN_RECORDS=off \
  -v "$PWD/tests/fixtures/studio/values.json:/check/values.json:ro" \
  -v "$PWD/docker/check-image.py:/check/check-image.py:ro" anisotropy-solver
docker exec api /app/api/.venv/bin/python /check/check-image.py --values /check/values.json --summary /tmp/summary.json
docker rm -f api
```

`ccx -v` prints the solver's version and exits with code 201, so a check of it needs `|| true`.
