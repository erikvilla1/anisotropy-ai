# syntax=docker/dockerfile:1
# The solver image (ADR-0056): the API and every program a coupon job needs, in one plain Docker image with nothing
# platform-specific inside, so the same image runs on Cloudflare Containers, Cloud Run, a customer's servers or a laptop.
#
#   docker build --build-arg GIT_COMMIT=$(git rev-parse HEAD) -t anisotropy-solver .
#   docker run --rm -p 8080:8080 -e ANISOTROPY_RUN_RECORDS=off anisotropy-solver
#
# docker/README.md explains the pieces; docker/check-image.py runs one public coupon job inside the image with the network off.

ARG UBUNTU=24.04
ARG TECTONIC_VERSION=0.17.0

# ---- Tectonic: the static build from its GitHub release, the same one CI installs (.github/workflows/tests.yml, job manual).
FROM ubuntu:${UBUNTU} AS tectonic
ARG TECTONIC_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin \
 && /usr/local/bin/tectonic --version

# ---- The image.
FROM ubuntu:${UBUNTU}
# CalculiX 2.21 from Ubuntu, as CI runs it; the libraries the Gmsh wheel links (`ldd libgmsh.so`: GL, GLU, X11 pieces, fontconfig,
# OpenMP), which CI's runner has and a bare image does not; certificates for the database's and the assistant's TLS.
RUN apt-get update && apt-get install -y --no-install-recommends calculix-ccx ca-certificates \
      libgl1 libglu1-mesa libgomp1 libfontconfig1 libxcursor1 libxfixes3 libxft2 libxinerama1 libxrender1 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /usr/local/bin/
COPY --from=tectonic /usr/local/bin/tectonic /usr/local/bin/tectonic

# One managed Python 3.12 for the three environments, outside any home folder so the service user can read it. The service
# user owns /app: a coupon job writes its files under /app/.local/fea/ (fea/src/anisotropy_fea/paths.py), as on a laptop.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python UV_PYTHON_PREFERENCE=only-managed UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN uv python install 3.12 && useradd --create-home --uid 1001 app && mkdir /app && chown app:app /app
WORKDIR /app

# The dependencies first, so a code change does not install them again: the three lockfiles, and the engine, which the
# api and fea projects depend on by path.
COPY --chown=app:app engine/ engine/
COPY --chown=app:app api/pyproject.toml api/uv.lock api/
COPY --chown=app:app fea/pyproject.toml fea/uv.lock fea/
USER app
RUN --mount=type=cache,target=/home/app/.cache/uv,uid=1001,gid=1001 \
    uv sync --locked --no-dev --project engine \
 && uv sync --locked --no-dev --no-install-project --project api \
 && uv sync --locked --extra mesh --no-install-project --project fea

# The code. .dockerignore keeps out .local/, node_modules/, out/, the website and every secret. The fea environment keeps its
# dev group: matplotlib draws the document's figures.
COPY --chown=app:app . .
RUN --mount=type=cache,target=/home/app/.cache/uv,uid=1001,gid=1001 \
    uv sync --locked --no-dev --project api && uv sync --locked --extra mesh --project fea

# Nothing syncs at run time: `uv run` starts the environment it finds (the API starts the coupon tool with it, ADR-0050).
ENV UV_NO_SYNC=1 UV_FROZEN=1
# Tectonic's TeX packages and fonts, fetched once here into the service user's cache by building the public coupon's document,
# so a running container never downloads any. The coupon's files are removed again; the image carries no run.
RUN uv run --project fea python docker/warm-tectonic.py

# The commit the image was built from, for the run records (records.git_commit): there is no .git inside the image.
ARG GIT_COMMIT=""
ENV ANISOTROPY_GIT_COMMIT=${GIT_COMMIT}

EXPOSE 8080
CMD ["/app/api/.venv/bin/uvicorn", "anisotropy_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
