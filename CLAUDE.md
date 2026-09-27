# CLAUDE.md: Speakardo

Speakardo is an AI life assistant: a Flutter app and a FastAPI backend. Users talk naturally; Speakardo creates reminders, remembers useful context about their life, and notifies them at the right moment.

**Status:** Modules 1–4 are done (Auth, AI Chat reminder parsing, Reminders, Notifications). **Now building Module 8: AI Memory**, one milestone at a time, starting with 8.0 Foundations.

## Read first

| When | Read |
| --- | --- |
| Always | `docs/README.md` (docs map, module status, which doc wins) |
| Any Module 8 work | `docs/modules/08-ai-memory/design.md` (the spec) and `blueprint.md` (the why) |
| Requirements and API list | `docs/product/srs.md` |
| Build order | `docs/product/roadmap.md` (Revision 1.1) |
| Reminder parsing | `docs/modules/02-ai-chat/hybrid-parsing.md` |
| Scheduling and timezones | `docs/modules/03-reminders/local-time-reminders.md` |

Markdown is the source of truth. Ignore the PDFs in `docs/product/exports/`; they are outdated v1.0 snapshots.

## Repo layout

```
backend/        FastAPI app
  app.py          entry point, router registration, scheduler lifespan
  routers/        auth, chat, reminders, devices, users, health
  services/       scheduler (APScheduler), notifications (FCM), local_schedule, repeat_schedule, email, google_auth
  models.py       SQLAlchemy models          schemas.py   Pydantic schemas
  deps.py         get_current_user           data_guards.py ownership checks
  alembic/        migrations (versions/YYYYMMDD_NNNN_description.py)
  tests/          pytest
ai_service/     AI logic, imported by the backend through a sys.path insert
  parsing/        layer1_rules → layer2_datetime → layer3_llm, orchestrated by hybrid.py
  gateway/        multi-provider LLM router with fallback (factory.get_default_router)
mobile_app/     Flutter app
  lib/screens/    UI screens (memory_screen.dart is placeholder UI until 8.2)
  lib/services/   *_provider.dart (ChangeNotifier state), api_service.dart, auth_http.dart
  lib/widgets/    app_chrome.dart (theme + SpeakardoScaffold/TopBar), speakardo_icons.dart
  test/           flutter tests
docker/         docker-compose Postgres 16 + pgvector (dev and test databases)
docs/           product docs, module designs, setup guides
export-react/   design reference screens (gitignored). UI inspiration only, not app code
```

## Commands

```bash
# Database (local): Postgres 16 + pgvector in Docker. Setup: docs/setup/local-database.md
docker compose -f docker/docker-compose.yml up -d

# Backend: run from backend/
source venv/bin/activate                 # needs requirements-dev.txt installed for pytest
uvicorn app:app --reload                 # http://localhost:8000
pytest                                   # Postgres test DB (ai_reminder_test), never SQLite
alembic -c alembic.ini upgrade head      # apply migrations (works on an empty database)

# Mobile: run from mobile_app/
flutter pub get
flutter run -d emulator-5554
flutter test
flutter analyze
```

## Environment and secrets

- The backend loads the **repo-root `.env`** (`backend/env_config.py`, `override=True`). The README's mention of `backend/.env` is outdated.
- `mobile_app/.env` is loaded by flutter_dotenv (`GOOGLE_WEB_CLIENT_ID`).
- If `DATABASE_URL` is unset, the backend falls back to SQLite (`backend/ai_reminder.db`). Module 8 needs Postgres with pgvector; never build memory features on SQLite.
- Tests use `TEST_DATABASE_URL` (default: the Docker `ai_reminder_test` database). `tests/conftest.py` sets it after `env_config` loads `.env`, and refuses any target that isn't a local `*_test` database.
- `MEMORY_SAFE_PROVIDERS` (default `openai,anthropic`) lists the only providers allowed to receive memories or chat history. Pass `personal_data=True` to `AIRouter.generate` for those calls; embeddings (`ai_service/gateway/embeddings.py`) always require the embedding provider to be on this list.
- **Development uses Gemini's free tier for memory work**: the dev `.env` sets `MEMORY_SAFE_PROVIDERS=gemini,openai,anthropic` and `EMBEDDING_PROVIDER=gemini`. Test data only; the startup warning `event=ai_memory_providers_untrusted` is expected in dev and must not appear in production.
- LLM providers are set by `AI_FALLBACK_CHAIN` plus `*_API_KEY` variables.
- **Never print, copy or commit secrets:** `.env` files, `backend/firebase-service-account.json`, `google-services.json`, `GoogleService-Info.plist`.

## Backend conventions

- **Logging** is structured key=value: `logger.info("event=reminder_created user_id=%s", user.id)`. Never log message text, memory content, tokens or secrets.
- **Every query is scoped to the current user** (`Depends(get_current_user)`). No endpoint returns another user's data.
- **Schema changes only through Alembic migrations**, named like the existing ones. Production runs with `AUTO_CREATE_SCHEMA=false`.
- **Time:** store UTC, timezone-aware. Recurring reminders use local wall-clock fields (`services/local_schedule.py`).
- **Rate-limit new endpoints** with the slowapi `limiter`.
- **All LLM calls go through `ai_service/gateway`**, never a provider SDK directly. From 8.0, calls that carry memories or chat history must use the provider allowlist.
- **Tests:** add or update pytest tests for every service change, and mock LLM and FCM calls. The full suite must pass before a task is done.

## Flutter conventions

- State: `provider` + `ChangeNotifier`; register new providers in `main.dart`'s `MultiProvider`.
- HTTP goes through `ApiService` / `auth_http.dart`, which attach and refresh auth tokens.
- UI uses `AppChrome` colours and the `SpeakardoScaffold` / `SpeakardoTopBar` widgets; icons come from `speakardo_icons.dart` (SVGs in `assets/icons/`).
- `flutter analyze` must be clean (flutter_lints).

## Module 8 rules (details in design.md)

- Postgres + pgvector only (no separate vector database); embeddings are 1536-dimensional.
- Save policy: save clearly stated, non-sensitive facts; ask before saving sensitive ones; never save implied sensitive facts.
- Confidence is rule-based (stated 1.0, implied 0.8, inferred ≤ 0.6), never the LLM's own estimate.
- Memories are passed to the LLM as quoted data, never as instructions.
- Context (time, place, activity) is computed per request and never stored.
- Proactive suggestions: at most 1 a day, with quiet hours respected.

## How to work in this repo

1. **One milestone at a time** (8.0 → 8.1 → …). Start in plan mode: list the files, migrations, API changes and tests, then wait for approval before writing code.
2. **Keep changes small and reviewable.** Don't refactor unrelated code or rename files you weren't asked to touch.
3. **Don't break Modules 1–4.** Run `pytest` and `flutter test` before saying something is done, and report the results.
4. **If the spec is unclear or seems wrong, ask**, or propose a doc change. Don't silently deviate. When a decision changes, update `design.md` in the same change.
5. **When a milestone ships,** update the Module status table in `docs/README.md` and tick its "Done when" in `design.md`.
6. **Commits** use conventional style (`feat(memory): ...`, `fix(scheduler): ...`). Only commit or push when asked.

## Known gotchas

- macOS ignores filename case: `docs/Setup` and `docs/setup` are the same folder. Use lowercase kebab-case.
- The backend imports `ai_service` through a `sys.path` insert (see `backend/routers/chat.py`).
- Chat routing (8.1a): memory rules first (`ai_service/router/rules.py`: "remember that…", "forget…", "what's my…", "what do you remember about me"), then the reminder parser for everything else. The AI turn router arrives in 8.1b. Memory rules are skipped while a reminder draft is pending.
- Memory persistence lives in `backend/services/memory_store.py`; `ai_service/memory/` is pure logic (keys, save policy, extraction prompt). Never log memory content or put it in `memory_events.detail`.
- Homebrew's `pgvector` formula only builds for `postgresql@17`/`@18`, so local Postgres runs in Docker (`pgvector/pgvector:pg16`), not Homebrew. Stop any Homebrew Postgres first: both use port 5432.
- `env_config.py` loads `.env` with `override=True`, so `DATABASE_URL=… alembic …` on the command line is silently ignored. Change `.env`, or set the variable after `env_config` is imported (as `tests/conftest.py` does).
- Use `backend/venv` (it has every requirement). `backend/.venv` is stale: no `google-genai` and `anthropic` 0.x. A provider whose SDK is missing silently drops out: Gemini from the fallback chain, Anthropic from `MEMORY_SAFE_PROVIDERS`.
- The `anthropic` SDK is 1.x, which removed `temperature`/`top_p`/`top_k` from `messages.create()`. The provider sends `temperature` through `extra_body` (Haiku 4.5 accepts it). `tests/test_anthropic_provider.py` checks the call against the installed SDK's signature.
- `reminder_events.reminder_id` has no foreign key on purpose: the event log outlives deleted reminders.
