# CreatorIQ backend: Phase 1 (foundation)

FastAPI + PostgreSQL + SQLAlchemy 2 + Alembic.

**What exists in Phase 1:** configuration from environment variables, a PostgreSQL
connection, Alembic migrations that create three empty schemas (`app`, `ds`, `synthetic`),
`GET /health`, `GET /health/db`, one consistent error format, and tests.

**What does not exist yet (by design):** authentication, dataset loading, prediction logic,
any other endpoint, any database table. The existing frontend (`CreatorIQ.html`) is not
touched and is not served by this backend yet.

## Prerequisites

- Python **3.11 or newer** (`python3 --version`). Verified with 3.11.17 and 3.12.3.
- Docker with Compose v2 (`docker compose version`), for the local PostgreSQL
- `curl` (optional, for trying the endpoints)

## Setup (first time)

Run everything from the `creatoriq-backend` folder.

### 1. Create a virtual environment and install dependencies

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

`requirements.txt` has only the runtime packages. `requirements-dev.txt` adds pytest, ruff and
the HTTP client behind FastAPI's `TestClient`, which is **`httpx2`** (Starlette prefers it and
prints a deprecation warning if only the older `httpx` is installed). All versions are pinned
to the ones the project was verified with.

### 2. Create your `.env`

macOS / Linux: `cp .env.example .env`
Windows (PowerShell): `Copy-Item .env.example .env`

Generate a password and paste it after `POSTGRES_PASSWORD=` in `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

`.env` is git-ignored. **Never commit it.** The same `POSTGRES_*` values are used by Docker
Compose (to create the database) and by the application (to connect to it). If the password
is left blank, both refuse to start and tell you why.

### 3. Start PostgreSQL

```bash
docker compose up -d db
docker compose ps          # wait until the STATUS column says "healthy"
```

The database listens on `127.0.0.1:5432` only (not your network). If port 5432 is already in
use, set `POSTGRES_PORT` (for example `5433`) in `.env` before starting it.

### 4. Create the schemas

```bash
alembic upgrade head
```

Expected last line: `Running upgrade  -> 0001, Create the empty app, ds and synthetic schemas.`
Running it again is harmless. Check the result any time with `alembic current`
(prints `0001 (head)`).

### 5. Run the API

```bash
uvicorn app.main:create_app --factory --reload
```

(`--factory` is required: there is deliberately no module-level `app` object.) The API is now
at <http://127.0.0.1:8000>, with interactive docs at <http://127.0.0.1:8000/docs>.

## Try it

```bash
curl -i http://127.0.0.1:8000/health
# {"status":"ok","service":"creatoriq-backend","version":"0.1.0"}

curl -i http://127.0.0.1:8000/health/db
# {"status":"ok","database":"up"}
```

| Endpoint | Meaning | Success | Failure |
|---|---|---|---|
| `GET /health` | The process is alive. Never touches the database. | `200` | n/a |
| `GET /health/db` | The database accepts a connection and answers `SELECT 1`. | `200` | `503` `database_unavailable` |

To see the failure mode, run `docker compose stop db` and call `/health/db`: you get `503`
immediately, `/health` still returns `200`, and everything recovers after
`docker compose start db`, with no app restart.

### Error format

Every error from the API has the same shape; `fields` appears only for validation errors:

```json
{"error": {"code": "not_found", "message": "Not Found", "request_id": "5c1f..."}}
```

Every response also carries an `X-Request-ID` header (a client-supplied one is reused if it
is 8-64 characters of `A-Z a-z 0-9 . _ -`). Error bodies never contain stack traces, exception
text, connection details or submitted values; those go to the server log, tagged with the
same `request_id`.

## Running the tests

```bash
python -m pytest                      # everything; database tests are skipped if not configured
python -m pytest -m "not integration" # only the tests that need no database
```

Without a test database configured, the first command runs 63 tests and skips 8. These 63
need no database (config, errors, health, migration SQL). The **integration tests** (real PostgreSQL: they run the migrations and check `/health/db`)
are **skipped** unless you provide a disposable test database:

```bash
# 1. create it (database name MUST end in _test)
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" creatoriq_test'

# 2. in .env, uncomment TEST_DATABASE_URL and fill it in, e.g.
#    TEST_DATABASE_URL=postgresql+psycopg://creatoriq:YOUR_PASSWORD@localhost:5432/creatoriq_test
#    (URL-encode the password if it contains special characters)

# 3. run everything
python -m pytest -v
```

The integration tests **create and drop the `app`, `ds` and `synthetic` schemas** in that
database. As a safety measure they fail immediately, touching nothing, if its name does not
end in `_test`. Tests never read your real `.env` configuration.

Lint and format checks:

```bash
ruff check .
ruff format --check .
```

## Configuration

All settings come from environment variables or `.env` (environment variables win).
No secret has a default value.

| Variable | Default | Notes |
|---|---|---|
| `POSTGRES_USER` | none (required*) | |
| `POSTGRES_PASSWORD` | none (required*) | Blank counts as not set |
| `POSTGRES_DB` | none (required*) | |
| `POSTGRES_HOST` | `localhost` | |
| `POSTGRES_PORT` | `5432` | 1-65535; also used by Docker Compose |
| `DATABASE_URL` | none | Optional full URL (`postgresql://` or `postgresql+psycopg://`); overrides the `POSTGRES_*` values for the app and Alembic |
| `APP_ENV` | `development` | `development`, `test` or `production` |
| `LOG_LEVEL` | `INFO` | `DEBUG` to `CRITICAL` |
| `DB_CONNECT_TIMEOUT` | `3` | Seconds, 1-60 |
| `DB_ECHO` | `false` | Log every SQL statement |
| `TEST_DATABASE_URL` | none | Tests only; see above |

\* not required if `DATABASE_URL` is set.

## Real data vs synthetic data

The database has three schemas, all empty in Phase 1:

| Schema | Holds |
|---|---|
| `app` | CreatorIQ's own application data (later phases) |
| `ds` | **Real** observational datasets only |
| `synthetic` | **Synthetic** data, test fixtures only |

**Rule: synthetic data must never be used to train a model or to produce a user-facing
prediction.** It is enforced in three places: the schemas are physically separate and their
database comments state the rule (`\dn+` in `psql`); `app/db/schemas.py` provides
`ensure_training_allowed(schema)`, which allows only `ds` and raises for everything else (all
future training/prediction code must call it); and tests cover both.

## Migrations

```bash
alembic upgrade head              # apply
alembic current                   # where am I
alembic downgrade base            # undo (see warning)
alembic revision -m "describe it" # new migration (later phases)
```

The downgrade drops the three schemas *without* `CASCADE`: if a schema has gained tables, it
fails instead of silently deleting data. The database URL is never stored in `alembic.ini`;
`migrations/env.py` reads the same settings as the app.

## Project layout

```
creatoriq-backend/
├── app/
│   ├── main.py            # create_app() factory
│   ├── api/               # health routes, FastAPI dependencies
│   ├── core/              # settings, error handling, request IDs, logging
│   └── db/                # engine, declarative base, schema names + data rule
├── migrations/            # Alembic (0001 creates the three schemas)
├── tests/
├── alembic.ini
├── docker-compose.yml     # local PostgreSQL
├── .env.example
├── requirements.txt / requirements-dev.txt
└── pyproject.toml         # pytest and ruff settings
```

## Troubleshooting

- **Startup fails with `Database is not configured ... (missing: POSTGRES_PASSWORD)`**:
  `.env` is missing or the password is blank (look at the last lines of the error output).
- **`docker compose` says `Set POSTGRES_PASSWORD in .env`**: same cause.
- **`/health/db` returns 503**: PostgreSQL is not running or the settings don't match it.
  Check `docker compose ps`, and that the password in `.env` is the one the database was
  *first created* with. Changing it later has no effect on an existing volume. To start over
  (**this deletes all database data**): `docker compose down -v`, then `docker compose up -d db`.
- **`ModuleNotFoundError: No module named 'app'`**: run commands from the `creatoriq-backend`
  folder, with the virtual environment active.
- **`address already in use`**: another process uses that port; pass `--port 8001` to uvicorn,
  or set a different `POSTGRES_PORT` for the database.
