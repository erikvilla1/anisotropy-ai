# Evaluation: run records database, chunk 1 (PostgreSQL in Docker) | 2026-10-14

- Scope: the database server only. No table, no API change, no new physics (ADR-0025).
- Environment: Windows 11, Docker Desktop 29.8.0, Compose v5.5.1, image `postgres:17` (PostgreSQL 17.11, Debian). `.env` at the repository root holds the generated password; it is git-ignored (`git check-ignore .env` printed `.env`).
- Files: `docker-compose.yml`, `.env.example`.

## Commands and captured output

Missing password. With `POSTGRES_PASSWORD=` empty in `.env`, `docker compose up -d`:

```text
error while interpolating services.db.environment.POSTGRES_PASSWORD: required variable POSTGRES_PASSWORD is missing a value: set POSTGRES_PASSWORD in .env (see .env.example)
exit=1
```

Start and connect. With a password set, `docker compose up -d`, then `docker compose ps` and `psql -c "\conninfo" -c "SELECT version();"` inside the container:

```text
composite_ai-db-1   postgres:17   Up 7 seconds (healthy)   127.0.0.1:5432->5432/tcp
You are connected to database "anisotropy" as user "anisotropy" via socket in "/var/run/postgresql" at port "5432".
PostgreSQL 17.11 (Debian 17.11-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
```

Data survives a stop. `CREATE TABLE scratch (...)`, `INSERT ... RETURNING *`, then `docker compose down`, `docker compose up -d`, `SELECT * FROM scratch;`:

```text
 id | note
----+-------
  1 | hello
(1 row)
```

A wipe removes it. `docker compose down -v` (output included `Volume composite_ai_anisotropy-pgdata Removed`), `docker compose up -d`, `SELECT * FROM scratch;`:

```text
ERROR:  relation "scratch" does not exist
```

Reachable from Windows. A Python socket connected to `127.0.0.1:5432` (`tcp ok`); the port is bound to the loopback address only.

## What this establishes

Compose refuses to start the database without a password; the server starts healthy from a clean state; a named volume keeps data across `down`/`up` and `down -v` removes it; the Windows side can reach the port that the API will use.

## Issues during verification

Docker Desktop was not running at the start; `docker compose up` failed with "failed to connect to the docker API". Starting Docker Desktop and waiting for the engine (about 20 seconds) resolved it. Before running the API with recording on, Docker Desktop must be running.

## Limits

No application code touches the database yet; `DATABASE_URL` in `.env.example` is documentation only until the next chunk. Connecting with a Windows-side client (psycopg) is UNVERIFIED; only a TCP connection and in-container `psql` were checked. CI does not start a database yet. Day-to-day reliability of Docker Desktop on this machine is UNVERIFIED beyond this session.
