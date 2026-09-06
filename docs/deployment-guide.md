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

## Cron: death anniversary reminders (`remind_death_anniversary`)

There is no Celery — one job a day does not justify a broker. The reminder command is
run by cron on the host (or by any external scheduler) against the same image:

```cron
# Nhắc giỗ -- 07:00 Việt Nam (UTC+7), mỗi ngày.
# If host is UTC, use 0 0; if UTC+7, use 0 7.
0 7 * * * cd /srv/calendar-api && docker compose run --rm web python manage.py remind_death_anniversary
```

**Critical:** Schedule on Vietnam time (UTC+7). `settings.TIME_ZONE` is `UTC`, so a
host in a different zone will fire on the wrong calendar day. The command itself
uses `services.gio.today_vn()` (not `timezone.localdate()`), so it computes the
right date — but the *schedule* must land on the intended morning. Examples:
- Host is UTC → `0 0 * * *` (fires at midnight UTC = 07:00 VN)
- Host is UTC+7 → `0 7 * * *`

The command is **not** clan-scoped and takes no arguments. One run sweeps every
non-deleted clan, using each clan's own `gio_remind_before_days` (default 3). Corrupt
clan data is logged and skipped, not fatal.

The command is safe to re-run. A `GioNotificationLog` row with `status='sent'` blocks
that (person, recipient, date) permanently. A `failed` row does NOT block — re-run
after an outage and only failed recipients are retried. **Do re-run it:** each person
is due exactly once per year, so a missed morning never gets retried until next year.

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

### Lunar calendar: known limitation

`giapha/services/vn_lunar.py` uses `TIMEZONE = 7` as a constant. Vietnam actually
used UTC+8 during 1943–45, 1947–55, and 1960–67. Dates entered as solar death dates
for ancestors from those periods will be off by ~8 hours, enough to flip the lunar
date by one day when a new moon fell near the timezone boundary.

**Impact on current endpoints:**
- `GET /clans/{id}/lich-gio` is unaffected (only scans forward from today, no pre-1968
  computation).
- Any future "enter ancestor's solar death date" feature **will** be affected if the
  date is before 1968. The genealogy app's core audience is precisely the owners of
  pre-1968 ancestors.

**Caveat:** documenting this limitation now is better than silently computing wrong
dates. Fixing it requires a timezone lookup table (not implemented). Flag as a blocker
if users report incorrect lunar dates for pre-1968 ancestors.

### FCM push: end-to-end delivery is UNVERIFIED

No Firebase project has been created for this application. Every test in
`giapha/tests/test_fcm_service.py` and `test_remind_command.py` patches the FCM layer;
**no test has ever delivered to a real device.** Proven: recipient resolution, de-duplication,
dead-token retirement, and the "unconfigured → exit 0" path. Unproven: that a handset
ever receives a push.

Treat the first run against a real Firebase project as a smoke test:

```bash
docker compose run --rm web python manage.py remind_death_anniversary
```

It prints `<date>: N lượt nhắc giỗ, đã gửi S, bỏ qua K (đã gửi trước đó).` on every run.
`N = 0` means nothing was due (not a sending failure). To force a due giỗ on a test clan,
set `gio_remind_before_days` so a known person's death date lands on `today + N`.

## Upgrading to phase 8 (presigned photo upload)

1. Rebuild the image — `requirements.txt` gained `boto3`/`botocore`/`s3transfer`/
   `jmespath`. Unlike `google-auth`, `boto3` is imported at the top of
   `giapha/services/storage.py` (not lazily) since it is now a hard, always-pinned
   dependency, not an optional one.
2. `python manage.py migrate giapha` — `photo_key` on `Person` already exists from
   an earlier migration; phase 8 adds no new migration, only new endpoints.
3. Provision an S3 bucket, or an R2 bucket, and set the five `S3_*` variables
   (below), or leave them empty and accept that the photo endpoints answer 503
   while the rest of the API works normally.

### Bucket requirements

* **Private, not public.** Every read goes through a presigned, time-limited `GET` URL
  (`photo_url` in the person response, 1-hour TTL); a public bucket plus a guessable key
  is a PII leak (family photos). There is no code path that makes the bucket work if
  public — do not enable public access "for convenience".

* **CORS must allow `PUT` from the app's origin.** The client uploads directly to the
  bucket with the presigned URL; without a CORS rule permitting `PUT` and `Content-Type`,
  the browser blocks the request with an opaque CORS error. This is the **single most
  common setup mistake**. Set the CORS configuration (adjust origins and methods to your
  setup):

  **AWS S3 (via AWS Console):**
  ```json
  [
    {
      "AllowedOrigins": ["https://your-app-origin.example"],
      "AllowedMethods": ["PUT"],
      "AllowedHeaders": ["Content-Type"],
      "MaxAgeSeconds": 3000
    }
  ]
  ```

  **Cloudflare R2 (via R2 Bucket Settings > CORS):** same JSON format.

* **Grant `s3:ListBucket` to distinguish "missing key" from "permission denied".** Without
  it, `head_object` on a missing key returns 403 instead of 404. The app treats both as
  not-found (confirm still works), but logs a `WARNING` on 403 since it *could* also mean
  a real credential fault. **Granting `s3:ListBucket` removes the ambiguity:** missing key
  → 404 (silent), permission fault → 403 (logged). It is worth the extra permission for
  clarity during troubleshooting.

* **Never commit credentials.** `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` go in `.env`
  only, never in code or git history.

### Configuration

| Variable | Value |
|---|---|
| `S3_ENDPOINT_URL` | Empty for real S3. For R2: `https://<account_id>.r2.cloudflarestorage.com` |
| `S3_BUCKET` | Bucket name |
| `S3_ACCESS_KEY_ID` | Access key |
| `S3_SECRET_ACCESS_KEY` | Secret key |
| `S3_REGION` | Real AWS region for S3 (e.g. `ap-southeast-1`); `auto` for R2 |

`boto3` is the client for both providers — R2 implements the S3 API, so only the
endpoint/region change, never the SDK. With all five unset, `giapha.services.storage`
answers `is_configured() == False` and the photo endpoints (`photo-upload-url`,
`photo`, `photo-urls`) return **503** with a Vietnamese message; every other giapha
endpoint (persons, tree, etc.) is unaffected.

### Known limitation: presigned `PUT` does not enforce the 5MB cap by itself

`generate_presigned_url('put_object', ...)` has no `Conditions` parameter (that
only exists for `generate_presigned_post`, a browser-form upload, not a plain
`PUT`), so the presigned URL itself cannot reject an oversized upload. The real
enforcement is the confirm step (`POST .../photo`), which `head_object`s the
uploaded object and rejects it — after the fact, but before `photo_key` is ever
written — if it is over 5MB or not an allowed content type. An abandoned/never-
confirmed upload can therefore leave an orphaned object over the cap sitting in
the bucket; there is no cleanup job for this yet (accepted at MVP, see the
phase-08 plan's risk assessment).

### S3/R2 upload: end-to-end delivery is UNVERIFIED

No real S3/R2 bucket has been provisioned for this application. `giapha/tests/test_photo_api.py`
mocks `boto3` entirely (no network is touched). Mocks cannot catch a wrong signature version,
a missing CORS rule, or a region/endpoint mismatch — all three fail at the client's `PUT`
request, the least visible point in the flow. Treat the first upload against a real bucket
as a smoke test, not as proof the path works:

```bash
curl -X POST https://your-app/api/gia-pha/clans/{clan_id}/persons/{pid}/photo-upload-url \
  -d '{"content_type":"image/jpeg","size":123456}'
# Returns: {"upload_url": "https://s3.../...", "key": "..."}

# PUT the returned upload_url with the actual file bytes and matching Content-Type
curl -X PUT 'https://s3.../...' -H 'Content-Type: image/jpeg' --data-binary @photo.jpg

# Confirm the upload (after checking size/type)
curl -X POST https://your-app/api/gia-pha/clans/{clan_id}/persons/{pid}/photo \
  -d '{"key":"<key from upload_url>"}'

# Fetch person detail to verify photo_url is a working presigned link
curl https://your-app/api/gia-pha/clans/{clan_id}/persons/{pid}
```

If the PUT fails with a CORS error (no error body, browser console shows opaque error),
verify the CORS rule on the bucket. If it fails with 403 on the presigned URL itself,
check the bucket credential has `s3:PutObject` (and ideally `s3:ListBucket`). If the
confirm endpoint returns 503, check that all five S3_* variables are set and the
credentials are readable by the container.
