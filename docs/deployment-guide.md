# Deployment Guide

The application itself runs from `docker-compose.yml` (`docker-compose up -d`).
This document covers only what has to be scheduled or configured *outside* the
web container.

## Upgrading to phase 6 (reminders)

1. Rebuild the image — `requirements.txt` gained `google-auth==2.29.0`, and without
   it the send path logs `google-auth is not installed; FCM disabled.` and delivers
   nothing (it does not crash: the import is lazy on purpose).
2. `python manage.py migrate giapha` — applies `0004` (the `ClanMember.person`
   binding) and `0005` (`GioFollow`, `DeviceToken`, `GioNotificationLog`,
   `Clan.gio_remind_before_days`).
   `0004` is purely additive with **no backfill**: every existing member starts
   unbound and picks themselves via `PUT /clans/{id}/toi-la`. Reverting `0004` on a
   live database loses every binding entered — dump `giapha_clanmember.person_id`
   first. `0005` drops cleanly on its own; revert it *before* `0004`.
3. Set the Firebase variables (below), or leave them empty and accept that the job
   is a clean no-op.

## Scheduled jobs

There is no Celery in this project, and one job a day does not justify adding
one. The reminder command is run by cron on the host (or by any external
scheduler), against the same image:

```cron
# Nhắc giỗ -- 07:00 giờ Việt Nam, mỗi ngày.
0 7 * * * cd /srv/calendar-api && docker compose run --rm web python manage.py remind_death_anniversary
```

**Schedule it on Vietnam time (UTC+7).** `settings.TIME_ZONE` is `UTC`, so a
host clock in another zone will fire the job on a different calendar day than
the one the families are counting. The command itself computes "today" with
`services.gio.today_vn()` and is therefore correct whatever the host timezone
is — but the *schedule* still has to land on the intended morning. On a UTC
host that means `0 0 * * *`.

The command is **not** clan-scoped and takes no arguments: one run sweeps every
non-deleted clan, using each clan's own `gio_remind_before_days` (default 3) as
the lead time. A clan whose data is corrupt is logged and skipped, not fatal.

The command is safe to re-run: a `GioNotificationLog` row with
`status='sent'` suppresses that (person, recipient, giỗ date) permanently, so
a second run on the same day re-sends nothing. A `failed` row does NOT
suppress — re-run the command after an outage and only the failed recipients
are retried. Do re-run it: each person is due on exactly one calendar day per
year, so a morning outage that is never retried loses that giỗ notice until
next year.

### Firebase credentials

`remind_death_anniversary` pushes through FCM HTTP v1 and needs a service
account. Set exactly one of these in `.env` (see `.env.example`):

| Variable | Value |
|---|---|
| `FIREBASE_CREDENTIALS_PATH` | path to the service account JSON inside the container |
| `FIREBASE_CREDENTIALS_JSON` | the raw JSON contents (wins if both are set) |

Never commit the service account file. With neither variable set the command
prints `Chưa cấu hình Firebase (FIREBASE_CREDENTIALS_PATH/JSON); không gửi được
gì.`, exits **0**, and writes no notification log rows — reminders are simply not
delivered, and cron stays quiet. A malformed service account behaves the same way
(it is a configuration fault; retrying cannot fix it).

A credentials **file that cannot be read right now** — mid-rotation, a flaky mount
— is treated differently: transient, so those recipients get a retriable `failed`
log row and the rest of the run continues. Re-running the command retries exactly
them.

The `web` service in `docker-compose.yml` forwards both variables into the
container. Mount the JSON file into the container as well if you use the path
form. `djangopj/settings.py` declares both (reading the same environment
variables), and the lookup checks `django.conf.settings` before the process
environment — so a deployment may hardcode them in settings instead.

### End-to-end delivery is UNVERIFIED

No Firebase project has been created for this application, and every test in
`giapha/tests/test_fcm_service.py` and `test_remind_command.py` patches the FCM
layer. Recipient resolution, de-duplication, dead-token retirement and the
"unconfigured → exit 0" path are all tested; **that a handset actually receives a
push is not**. Treat the first run against a real Firebase project as a smoke
test, not as a regression check:

```bash
docker compose run --rm web python manage.py remind_death_anniversary
```

It prints `<date>: N lượt nhắc giỗ, đã gửi S, bỏ qua K (đã gửi trước đó).` on
every run. `N = 0` means nothing was due — not that sending is broken. To force a
due row on a test clan, set that clan's `gio_remind_before_days` so that a known
giỗ lands on `today + N`.
