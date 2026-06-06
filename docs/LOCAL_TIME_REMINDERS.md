# Local time reminders

Reminders follow the user's **local wall clock** when they travel. One-time reminders stay at an exact UTC moment.

## Two reminder types

| Type | `repeat` | When it fires |
|------|----------|----------------|
| **One-time** | `null` | Exact UTC `datetime` (e.g. doctor appointment) |
| **Repeating** | `daily`, `weekly`, … | Every day at `local_time` in the user's **current** timezone |

## Example (your scenario)

1. User in **Asia/Karachi** creates *Take Medicine* at **09:00**, daily.
2. Server stores `local_time = "09:00"` (wall clock), not a fixed UTC offset forever.
3. Scheduler each tick: `local = utc_now in user.timezone` → if `local` is 09:00 → fire.
4. User travels to **Asia/Dubai**; app calls `PATCH /users/me/timezone` with `Asia/Dubai`.
5. Next day reminder fires at **09:00 Dubai time** (not 10:00).

## Database fields

| Column | Purpose |
|--------|---------|
| `datetime` | One-time: exact fire UTC. Repeating: last/display reference |
| `local_time` | `HH:MM` wall clock for repeating |
| `local_weekday` | Anchor weekday for `weekly` |
| `local_day_of_month` | Anchor day for `monthly` |
| `snoozed_until` | Absolute UTC snooze for repeating (overrides local clock until then) |
| `users.timezone` | Current IANA timezone (updated from device) |

## Scheduler (every ~30s)

```
now = UTC now
for each pending reminder:
  user_tz = user.timezone
  if repeating:
    if snoozed_until due → fire
    elif snoozed_until in future → skip
    elif local HH:MM in user_tz matches local_time (+ repeat rule) → fire
  else:
    if datetime <= now → fire
```

## API

- `PATCH /users/me/timezone` — body `{ "timezone": "Asia/Dubai" }`
- Mobile syncs automatically on app open and resume (`DeviceTimezoneService`)

## Migration

```bash
cd backend && alembic upgrade head
```

Backfills `local_time` from existing `datetime` + user timezone.
