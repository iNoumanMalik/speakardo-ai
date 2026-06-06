# Developer Debugging Guide

This guide explains how to use log filters, terminal commands, and debugging workflows for the **AI Reminder App** (FastAPI backend + Flutter mobile).

---

## Quick answer: “Do I type these in the terminal?”

**Yes.** The filters like `event=ai_extractor_success` are **search patterns**. You run them against log output in your terminal, for example:

```bash
# While the API is running, in another terminal:
# (copy logs from the terminal where uvicorn runs, or pipe live)

grep "event=ai_extractor_success" 
```

Better on macOS/Linux, use `rg` (ripgrep) if installed:

```bash
rg "event=ai_extractor_success"
```

You do **not** type these inside Python or Flutter code — they filter **text output** from your running app.

---

## 1. Backend log filters (copy-paste)

### Enable log level

Before starting the API:

```bash
export LOG_LEVEL=INFO    # normal
# export LOG_LEVEL=DEBUG   # verbose (SQL, more detail)
```

Start the backend from `backend/` (however you usually run it, e.g. `uvicorn app:app --reload`).

Log lines look like:

```text
ts=2026-05-24T12:00:00Z level=INFO logger=ai_service.extractor msg=event=ai_extractor_success provider=gemini ...
```

### Useful filters (search terms)

| What you want | Search for |
|---------------|------------|
| Which AI provider parsed chat | `event=ai_extractor_success` |
| AI router config at startup | `event=ai_router_configured` |
| AI failures / fallback | `event=ai_extractor_all_providers_failed` or `fallback=mock_extractor` |
| Push notification sent | `event=push_send` |
| Snooze from API | `event=snooze` |
| Reminder completed | `event=reminder_completed` |
| Scheduler picked a reminder | `Scheduler considering` or `Processing start` |
| Scheduler finished | `Processing finished` |
| Stuck processing recovery | `Recovering stale` or `processing_timeout_recovered` |
| Chat request | `event=chat_request` |
| Firebase init | `event=firebase_` |
| Google sign-in (API) | `event=google_auth_` |

### How to filter live logs

**Option A — API runs in Terminal 1; filter in Terminal 2**

Terminal 1:

```bash
cd backend
source .venv/bin/activate
export LOG_LEVEL=INFO
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 — watch only snooze events:

```bash
# If you save logs to a file:
tail -f /path/to/your-api.log | rg "event=snooze"

# Or: run API with tee so you can tail one file:
# uvicorn app:app --reload 2>&1 | tee /tmp/api.log
tail -f /tmp/api.log | rg "event=push_send"
```

**Option B — One-shot search in a saved log file**

```bash
rg "event=ai_extractor_success" /tmp/api.log
rg "event=push_send|event=snooze" /tmp/api.log
```

**Option C — Case-insensitive**

```bash
rg -i "snooze" /tmp/api.log
```

**Option D — Show context (lines before/after match)**

```bash
rg -C 3 "Processing failed" /tmp/api.log
```

### If you don’t have `rg`, use `grep`

```bash
grep "event=snooze" /tmp/api.log
grep -E "event=push_send|event=snooze" /tmp/api.log   # multiple patterns
```

---

## 2. Backend debugging checklist

### Environment

| Variable | Purpose |
|----------|---------|
| `LOG_LEVEL` | `INFO` (default) or `DEBUG` |
| `DATABASE_URL` | Postgres connection |
| `AI_FALLBACK_CHAIN` | e.g. `gemini,openai,groq` |
| `GEMINI_API_KEY`, `OPENAI_API_KEY`, etc. | LLM providers |
| `FIREBASE_CREDENTIALS_PATH` | Push notifications |
| `SCHEDULER_INTERVAL_SECONDS` | How often due reminders are checked (default 30) |

### Verify AI provider at startup

After starting the API, look for:

```text
event=ai_router_configured provider_chain=... active_providers=...
```

`active_providers` lists which providers actually have API keys configured.

### Test chat → extraction

1. Log in on the app.
2. Send: `Remind me to test at 9 PM tomorrow`.
3. In logs, search:

```bash
rg "event=chat_request"
rg "event=ai_extractor_success"
```

You should see `provider=...` and `model=...` on the success line.

### Test snooze flow

1. Create a reminder that fires soon.
2. Tap **Snooze 5m** on the notification.
3. Search:

```bash
rg "event=snooze"
```

Confirm `new_datetime=...` is about 5 minutes in the future (UTC).

4. You should **not** see repeated `event=push_send` every few seconds before that time.

### Test scheduler

```bash
rg "Scheduler tick|Processing start|Processing finished|Recovering stale"
```

### API manually (curl)

Get a JWT from login, then:

```bash
curl -X POST "http://127.0.0.1:8000/reminders/<REMINDER_ID>/snooze" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"minutes": 5}'
```

Watch logs for `event=snooze`.

### Database (Postgres)

```bash
# Example: see reminder state
psql "$DATABASE_URL" -c "SELECT id, task, status, datetime, triggered_at, processing_started_at FROM reminders ORDER BY datetime DESC LIMIT 10;"
```

### Run backend tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## 3. Flutter / mobile debugging

### Run the app with verbose output

```bash
cd mobile_app
flutter pub get
flutter run -v
```

Pick a device when prompted (emulator or physical phone).

### Flutter analyze (static checks)

```bash
cd mobile_app
flutter analyze
```

### Flutter tests

```bash
cd mobile_app
flutter test
```

### Flutter DevTools (UI, performance, network)

While `flutter run` is active, open another terminal:

```bash
cd mobile_app
dart devtools
```

Or press the link printed in the `flutter run` output (`The Flutter DevTools debugger and profiler on ... is available at: http://...`).

Useful tabs:

- **Inspector** — widget tree, layout issues
- **Network** — HTTP calls to your API (if instrumented)
- **Logging** — `debugPrint` output
- **Performance / CPU & Memory** — jank and leaks

### `debugPrint` in code

The app uses `debugPrint` for things like notification actions. In **debug builds**, these show in the same console as `flutter run`.

Examples you might see:

```text
Notification action=action_snooze_5 reminder_id=...
Snooze saved reminder_id=... — next fire in 5 minutes
```

### Android: logcat (notifications, FCM, actions)

With device/emulator connected:

```bash
adb logcat | rg -i "flutter|fcm|notification|snooze|reminder|Firebase"
```

Clear logcat first (optional):

```bash
adb logcat -c
# reproduce the bug
adb logcat | rg "action_snooze"
```

### iOS: Xcode console

1. Open `mobile_app/ios/Runner.xcworkspace` in Xcode.
2. Run on a simulator or device.
3. View **Debug area → Console** for logs.

### Breakpoints (step-through debugging)

**VS Code / Cursor:**

1. Open `mobile_app/`.
2. Set a breakpoint (click left of line number), e.g. in `notification_action_handler.dart` inside `_snooze`.
3. Run **Run → Start Debugging** (or F5) with Flutter extension installed.
4. Trigger snooze from a notification — execution should pause.

### API base URL (device vs emulator)

In `mobile_app/lib/config/app_config.dart`:

| Platform | Typical API URL |
|----------|-----------------|
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator | `http://127.0.0.1:8000` |
| Physical device | Your computer’s LAN IP, e.g. `http://192.168.1.10:8000` |

If login or snooze fails only on a real phone, this is often the cause.

### Full restart after native changes

After changing `AndroidManifest.xml`, notification channels, or Firebase config:

```bash
flutter clean
flutter pub get
flutter run
```

Hot reload is **not** enough for manifest/notification channel changes.

### Reset onboarding (test first-run flow)

Clear app data on the device, or uninstall/reinstall the app.

---

## 4. End-to-end debugging workflows

### Workflow A — “Chat doesn’t understand my message”

1. Backend: `LOG_LEVEL=INFO`, reproduce in app.
2. `rg "event=chat_request"` and `rg "event=ai_extractor"` on API logs.
3. Check `event=ai_extractor_success` vs `event=ai_extractor_all_providers_failed`.
4. If fallback/mock: fix API keys / `AI_FALLBACK_CHAIN`.

### Workflow B — “No push notification”

1. `rg "event=firebase_"` — Firebase initialized?
2. `rg "event=push_send"` — was send attempted?
3. App: notification permission granted? (Profile + system settings)
4. Device registered: look for FCM token registration in app debug output.
5. Android: correct notification channel; rebuild after channel id changes.

### Workflow C — “Snooze doesn’t work / repeats forever”

1. App: `debugPrint` on snooze action (already in code).
2. Backend: `rg "event=snooze"` — did API receive request?
3. Check `new_datetime` is in the future (UTC).
4. `rg "event=push_send"` — should **not** spam before snooze time.
5. DB: `status` should be `pending` after snooze, not `processing` stuck.

### Workflow D — “Reminder stuck in processing”

1. `rg "Recovering stale|Processing failed|processing_exception"`.
2. Run migration if schema changed: `cd backend && alembic upgrade head`.
3. Optionally reset row in SQL (see team lead before production).

---

## 5. Recommended tools to install

| Tool | Use |
|------|-----|
| `rg` (ripgrep) | Fast log search (`brew install ripgrep`) |
| `httpie` or `curl` | Manual API tests |
| `psql` | Database inspection |
| Flutter extension (VS Code/Cursor) | Debug/run Flutter |
| Android Studio / Xcode | Emulators, logcat, iOS console |
| `adb` | Android device logs |

---

## 6. Log levels (when to use what)

| Level | When |
|-------|------|
| `DEBUG` | Deep investigation, SQL, noisy libs |
| `INFO` | Normal development (default recommendation) |
| `WARNING` | Recoverable issues (empty AI response, retry) |
| `ERROR` | Failures (FCM send failed, all providers failed) |

---

## 7. Cheat sheet (one page)

```bash
# --- Backend ---
cd backend && source .venv/bin/activate
export LOG_LEVEL=INFO
uvicorn app:app --reload --host 0.0.0.0 --port 8000 2>&1 | tee /tmp/api.log

# In another terminal:
rg "event=ai_extractor_success" /tmp/api.log
rg "event=push_send" /tmp/api.log
rg "event=snooze" /tmp/api.log
rg "Processing start|Processing finished|Recovering stale" /tmp/api.log

# --- Flutter ---
cd mobile_app
flutter run -v
flutter analyze
flutter test

# Android logs:
adb logcat | rg -i "flutter|notification|snooze|fcm"
```

---

## 8. Getting help from logs

When reporting a bug, attach:

1. **What you did** (steps)
2. **Expected vs actual**
3. **Relevant log lines** (10–30 lines), e.g. snooze + push_send + scheduler
4. **Platform** (Android/iOS, emulator/device)
5. **Approximate time (UTC)** for backend log correlation

Example snippet to copy:

```text
event=snooze reminder_id=... minutes=5 new_datetime=2026-05-24T15:10:00+00:00
event=push_send provider=fcm success=true reminder_id=... (should appear once at new_datetime)
```

---

*Last updated for structured backend logs (`event=...`) and Flutter notification/snooze debugging.*
