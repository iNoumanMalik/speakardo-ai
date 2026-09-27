# Local database (Postgres 16 + pgvector)

Version 1.0 · 2026-09-26 · Module 8.0 Foundations

Speakardo runs on Postgres 16 with the `pgvector` extension (memory search, from Module 8.1). Local development and the backend tests both use the Docker image `pgvector/pgvector:pg16`.

Why Docker rather than Homebrew: Homebrew's `pgvector` formula only builds for `postgresql@17` and `@18`, so it cannot add the extension to a Homebrew `postgresql@16`.

## 1. Start Postgres

```bash
# Homebrew Postgres also uses port 5432; stop it first if it is running
brew services stop postgresql@14

docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps     # STATUS shows "healthy"
```

On its first start the container creates two databases:

| Database | Used by | Notes |
| --- | --- | --- |
| `ai_reminder` | the API (`uvicorn`) | your development data |
| `ai_reminder_test` | `pytest` | wiped and re-migrated on every test run |

`ai_reminder_test` is created by `docker/initdb/01-test-database.sql`, which only runs when the volume is new. If your volume already existed, create it once by hand:

```bash
docker exec ai_reminder_db createdb -U user ai_reminder_test
```

## 2. Point the backend at it

In the repo-root `.env` (the backend loads this file and it overrides shell variables):

```
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/ai_reminder
```

Then apply migrations. They build the full schema from an empty database, including the `vector` extension:

```bash
cd backend
source .venv/bin/activate          # or your venv
pip install -r requirements-dev.txt
alembic -c alembic.ini upgrade head
```

## 3. Keep your old Homebrew data (optional)

Copy the Homebrew Postgres 14 database into the Docker one, then upgrade it:

```bash
PG14=/opt/homebrew/opt/postgresql@14/bin
$PG14/pg_ctl -D /opt/homebrew/var/postgresql@14 -o "-p 5433" -w start
$PG14/pg_dump -p 5433 -d ai_reminder -Fc --no-owner --no-privileges > /tmp/ai_reminder.dump
$PG14/pg_ctl -D /opt/homebrew/var/postgresql@14 -m fast stop

docker exec -i ai_reminder_db pg_restore -U user -d ai_reminder --no-owner --no-privileges < /tmp/ai_reminder.dump
cd backend && alembic -c alembic.ini upgrade head
```

## 4. Run the tests

```bash
cd backend && pytest
```

`tests/conftest.py` drops the test database's schema, migrates it with the real Alembic chain, and empties every table after each test. To protect real data, it refuses to run unless the target is on `localhost` and its name ends in `_test`. Override the target with `TEST_DATABASE_URL`, for example in `.env`:

```
TEST_DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/ai_reminder_test
```

If Postgres isn't running, the database tests stop with a message telling you to start it. Pure unit tests (parsing, scheduling maths) don't need a database.

## 5. Environment variables added in 8.0

| Variable | Default | Purpose |
| --- | --- | --- |
| `TEST_DATABASE_URL` | `postgresql+psycopg2://user:password@localhost:5432/ai_reminder_test` | Database the test suite migrates and wipes |
| `MEMORY_SAFE_PROVIDERS` | `openai,anthropic` | The only AI providers allowed to receive memories or chat history. A value with no valid names allows none. Development uses `gemini,openai,anthropic` (see below) |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `gemini`. Must also be listed in `MEMORY_SAFE_PROVIDERS` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` (openai) / `gemini-embedding-001` (gemini) | Embedding model for the chosen provider |
| `EMBEDDING_DIMENSIONS` | `1536` | Must stay 1536 (the size of the memory vector column) |

`ANTHROPIC_MODEL` should be a current model ID such as `claude-haiku-4-5`; older Claude 3.5 IDs are outdated.

**Free development setup.** To build memory features without paid API credits, add to `.env`:

```bash
MEMORY_SAFE_PROVIDERS=gemini,openai,anthropic
EMBEDDING_PROVIDER=gemini
```

Only your `GEMINI_API_KEY` needs to work. Google may use free-tier Gemini data, so use test data only. The server logs `event=ai_memory_providers_untrusted` at startup as a reminder. Remove `gemini` from the list before real users.

## 6. Supabase (shared database)

- pgvector is available on Supabase; the `20260926_0001_enable_pgvector` migration enables it with `CREATE EXTENSION IF NOT EXISTS vector`.
- Use the **Session pooler** connection string (port 5432) with `?sslmode=require`; the direct connection is IPv6-only on many networks.
- Run `alembic upgrade head` against Supabase once, by one person, after the PR that adds a migration is merged.
- Never point `TEST_DATABASE_URL` at Supabase. The test suite wipes its target database, and its guard refuses any host other than `localhost`.
