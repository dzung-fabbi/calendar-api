# Deployment Guide

`docker-compose.yml` is the **development** stack (`runserver`, source bind-mount,
ports on `0.0.0.0`, no database volume). Production runs from
`docker-compose.prod.yml`. The rest of this document covers what has to be
scheduled or configured *outside* the web container.

## Production: api.thienvanlichphap.vn / cms-calendar.thienvanlichphap.vn

Live on `ubuntu@13.212.105.46` (shared host — `tuvi.thienvanlichphap.vn`,
`ttc.ces-ai.io.vn` and others already run there; ports `8000`, `8001`, `3000`,
`3003`, `3101`, `8101`, `5433` are taken by them).

| | |
|---|---|
| App directory | `/srv/calendar-api` |
| Compose file | `docker-compose.prod.yml` (**standalone**, not an overlay) |
| Web container | gunicorn, 3 sync workers, published on `127.0.0.1:8002` only |
| Database | `mysql:5.7` in the named volume `calendar-api_mysql_data`, **not** published to the host |
| Static files | `collectstatic` → `/srv/calendar-api/staticfiles`, served by host nginx at `/static/` |
| nginx vhosts | source of truth in `deploy/nginx/`, installed to `/etc/nginx/sites-available/` |
| Secrets | `/srv/calendar-api/.env`, mode `600`, never committed |

`docker-compose.prod.yml` is deliberately **standalone rather than an overlay**:
compose merges `ports` additively, so `-f docker-compose.yml -f docker-compose.prod.yml`
would keep the dev publishes (`0.0.0.0:8000`, `0.0.0.0:3308`) and collide with the
other projects on this host.

### Split across the two domains

Both names are served by the *same* container — there is no separate CMS
application in this repository. `django.contrib.admin` plus django-object-actions
**is** the content-management surface, which matters because the almanac tables
(stars, thần sát, …) ship with **no fixtures**: on a fresh database they are empty
and the almanac endpoints return nothing until content is entered through the CMS.

- `api.thienvanlichphap.vn` — the API. `/admin/` returns **404 by nginx** here on
  purpose: `ALLOWED_HOSTS` accepts both names, so without that rule the same
  session-cookie admin login would be reachable on the public API origin too.
- `cms-calendar.thienvanlichphap.vn` — the admin. `/` 302s to `/admin/`.

### Deploy / redeploy

The server has no credentials for the private GitHub repo, so code is pushed over
SSH rather than pulled:

```bash
# From a clone, on your machine:
tar czf - --exclude-vcs --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='staticfiles' --exclude='plans' --exclude='.env' . \
  | ssh -i ~/.ssh/numerlogy.pem ubuntu@13.212.105.46 'tar xzf - -C /srv/calendar-api'

# On the server:
cd /srv/calendar-api
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput
docker compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
```

The `--exclude='.env'` is load-bearing: without it a local dev `.env` overwrites the
production secrets.

### TLS

**Done.** One Let's Encrypt certificate covers both names
(`/etc/letsencrypt/live/api.thienvanlichphap.vn/`, SANs `api.` + `cms-calendar.`),
80→443 redirects are in place, and `certbot renew --dry-run` passes under the
existing `snap.certbot.renew.timer`.

`deploy/enable-tls.sh <email>` is what did it, and is idempotent if it needs re-running:
`certbot --nginx` for both names, then flips `DJANGO_SECURE_COOKIES` /
`DJANGO_BEHIND_TLS_PROXY` to `True` in `.env` and restarts. Its DNS pre-check queries
`1.1.1.1`/`8.8.8.8` rather than the local stub resolver — see the resolver note below
for why that matters.

Three settings stay off on purpose, and `manage.py check --deploy` will keep
warning about two of them:

- `DJANGO_SECURE_COOKIES` — now `True`. It had to stay `False` until certbot had run:
  a `Secure` session cookie over a plaintext connection means nobody can log into
  the admin at all. Same for `DJANGO_BEHIND_TLS_PROXY`.
- `DJANGO_SECURE_SSL_REDIRECT=False` permanently — certbot's `--redirect` already
  does 80→443 at the edge; doubling it in Django only adds a way to build a loop.
- `DJANGO_HSTS_SECONDS=0` permanently, **unless every subdomain of
  `thienvanlichphap.vn` is HTTPS-only**. `settings.py` hardcodes
  `SECURE_HSTS_INCLUDE_SUBDOMAINS`/`PRELOAD` to `SECURE_HSTS_SECONDS > 0`, so any
  non-zero value asserts HSTS across the whole apex — including sibling subdomains
  this deploy does not own.

`DJANGO_NUM_PROXIES=1` is set, matching the one nginx in front. That is what makes
the DRF per-IP throttles (`giapha-join`, `auth-forgot-password`, …) key off the real
client IP instead of `REMOTE_ADDR` or a forgeable header.

### Gotcha: the box cannot resolve `api.thienvanlichphap.vn` (harmless)

`curl https://api.thienvanlichphap.vn/...` **from the server** fails with
`Could not resolve host`, while the same URL works from everywhere else. The AWS
VPC resolver (`172.31.0.2`) negative-cached the NXDOMAIN from before the A record
existed; the authoritative NS (`ns1.matbao.vn`), `1.1.1.1` and `8.8.8.8` all answer
correctly, and `resolvectl flush-caches` does not clear the *upstream* cache. It
expires on its own.

Nothing depends on it: no code path resolves the API's own hostname, and Let's
Encrypt validates from outside (the certificate issued fine). It only breaks
on-box smoke tests — bypass it with `--resolve`:

```bash
curl -o /dev/null -w '%{http_code}\n' \
  --resolve api.thienvanlichphap.vn:443:127.0.0.1 \
  https://api.thienvanlichphap.vn/api/gia-pha/clans   # -> 401
```

Do **not** "fix" this by adding a `/etc/hosts` entry: that would send the box's own
traffic to `127.0.0.1` permanently and silently mask a real DNS problem later.

### Base image: bookworm, not bullseye

Debian bullseye left security support and its `bullseye-security` Release file is
past `Valid-Until`, which makes a plain `apt-get update` exit 100 and **fail the
build outright** -- both `Dockerfile` and `Dockerfile.test` broke without a single
commit touching them.

Both now use `python:3.9-bookworm`, which is still supported. An earlier fix on
this host instead passed `-o Acquire::Check-Valid-Until=false` on the reasoning
that no 3.9 bookworm image existed; it does (verified by building the test image
on it). Prefer moving to a supported release over accepting stale metadata: the
flag silences the error and keeps installing unpatched packages, turning a loud
build failure into a quiet EOL runtime.

Python stays pinned to 3.9 -- that constraint is Django 3.1, and it is unrelated
to the Debian release.

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

**Already installed** on 13.212.105.46 in `ubuntu`'s crontab. That host is `Etc/UTC`,
so the entry is `0 0` (= 07:00 VN), uses the production compose file, and needs
`-T` because cron has no TTY:

```cron
0 0 * * * cd /srv/calendar-api && /usr/bin/docker compose -f docker-compose.prod.yml run --rm -T web python manage.py remind_death_anniversary >> /var/log/calendar-api-gio.log 2>&1
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

**The same five `S3_*` variables also serve the generic upload endpoints**
`POST /api/files/upload-url` and `POST /api/files/confirm` (`apis/views/file_upload.py`,
`apis/services/storage.py` -- a deliberate copy of the giapha module, since `apis/` may
not import `giapha/`). One bucket, one credential, one CORS rule covers both. Those two
endpoints are **unauthenticated** (`AllowAny` + a 20/hour per-IP throttle), so anyone who
can reach the API can put an image in this bucket -- see `docs/api-reference.md` ->
"Tải Tệp Lên" for the full risk note. Objects land under the `uploads/` prefix; giapha
photos stay under `giapha/{clan_id}/{person_id}/`.

**Set a lifecycle rule on the `uploads/` prefix.** A caller can request an upload URL and
never confirm, leaving an orphaned object, and nothing in the code deletes it -- there is
no cleanup job and the generic endpoints have no delete.

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

### S3/R2 upload: end-to-end VERIFIED (2026-09-09)

The generic `/api/files` flow was run against the live bucket
(`calendar-giapha-prod`, `ap-northeast-1`) end to end: mint → `PUT` of a real PNG
straight to S3 (200) → confirm (200) → presigned `GET` (200), with the bytes
returned byte-identical to the bytes sent. The test object was deleted afterwards.

That proves the shared mechanism — signature version, endpoint resolution,
credentials, bucket policy — since `apis/services/storage.py` and
`giapha/services/storage.py` presign identically. The **giapha photo endpoints
themselves** (`photo-upload-url` / `photo` confirm / `photo-urls`) have still not
been exercised against the real bucket; only the storage layer underneath them
has.

Why this mattered: mocks cannot catch a wrong signature version, a missing CORS
rule, or a region/endpoint mismatch — all three fail at the client's `PUT`, the
least visible point in the flow. Two of those three were real and were only found
by hand on the production host (see the SigV4 / regional-endpoint notes in
`services/storage.py`). `apis/tests/test_file_upload_api.py`'s
`StorageClientConstructionTests` now pins both, so a regression fails a test
rather than an upload.

To re-run the check against a fresh bucket:

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

## Dropping the orphaned `social_auth_*` tables (IRREVERSIBLE)

Login is username/password only (`grant_type=password` against `/auth/token`). Five
`social_auth_*` tables are left over from a third-party auth package that no longer ships;
Django stopped managing them when the package left `INSTALLED_APPS` but does **not** drop
them, so they sit in the database holding third-party user ids and provider access tokens
in plaintext.

`giapha/migrations/0007_drop_social_auth_tables.py` drops them. It runs
`DROP TABLE IF EXISTS` on `social_auth_usersocialauth` (the child holding the FK to
`auth_user`, first), `social_auth_nonce`, `social_auth_association`, `social_auth_code`,
`social_auth_partial`, then deletes the orphan `django_migrations` rows.

**This is not reversible.** Reverting the commit does not bring the tables back; a restored
dump is the only rollback.

1. **BACK UP FIRST — mandatory, not advisory:**
   ```bash
   mysqldump -h <host> -u <user> -p <db> > backup-YYYYMMDD.sql
   ```
2. **Dry-run against a restored production dump.** The test suite provably cannot cover this
   migration: the test database never creates these tables, so `IF EXISTS` makes it a no-op
   there and a green suite says nothing about it.
3. Apply it:
   ```bash
   docker compose run --rm web python manage.py migrate giapha
   ```
4. Verify:
   ```sql
   SHOW TABLES LIKE 'social_auth%';  -- should return 0 rows
   SELECT COUNT(*) FROM django_migrations WHERE app='social_django';  -- should return 0
   ```

`migrate` is idempotent here — running it twice is clean.

**One thing the drop destroys:** `social_auth_usersocialauth` is the only table that can
answer *which* accounts have no usable password because they used to authenticate through a
provider. Once it is gone, that list is only recoverable by restoring the backup. If you
want it kept out of band, export it before step 3:

```sql
SELECT u.id, u.username, u.email
FROM auth_user u
JOIN social_auth_usersocialauth s ON s.user_id = u.id
WHERE u.password = '' OR u.password LIKE '!%';
```

Treat the output as PII: keep it off shared drives and delete it after use.

### Accounts with no usable password

Some rows in `auth_user` carry `set_unusable_password()` (`password` empty or starting with
`!`) and therefore cannot log in by password. Their data is intact; their login is not.

**Recovery, cheapest first:**
- **Password reset works for them.** `POST /api/auth/forgot-password` mails a 6-digit code
  and `POST /api/auth/reset-password` sets a new password. It is deliberately NOT gated on
  `has_usable_password()`, so mailbox possession alone is enough. Requires the `EMAIL_*`
  configuration below, and a `username` that is the user's email address — a row whose
  `username` is some other identifier is not reachable this way and needs the admin path.
- Admin sets a password via `manage.py changepassword <username>` or Django admin
  (`/admin/auth/user/`) and communicates it to the user.
- User re-registers; admin re-binds their `ClanMember` row and family data to the new account.

### Known gap: `/auth/token` is unthrottled

It is now the only login flow in the product and has no rate limit, so password-grant
credential stuffing is unbounded. Pre-existing, tracked separately. Note that adding a DRF
throttle scope only helps once `DJANGO_NUM_PROXIES` matches the real number of trusted
proxies — at the current `0`, buckets key off `REMOTE_ADDR`.

## Email (password-reset OTP)

The only feature that sends mail is the password-reset code
(`apis/services/mailer.py`). Set these in `.env`:

```
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=apikey-or-username
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=True
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=no-reply@yourdomain.tld
```

**`EMAIL_HOST` is the switch.** Leave it empty and Django uses the console backend: the
message is printed to the process log instead of being sent, and nothing raises. That is
what makes local dev and CI work without credentials — and it also means a deploy that
forgets `EMAIL_HOST` looks completely healthy while no user ever receives a code.

**A broken SMTP server is invisible to users, by design.** `forgot-password` answers the
same 200 whether the send succeeded or not, because a visible failure would reveal which
addresses belong to real accounts (a send is only attempted for those). The failure is
recorded as a `WARNING` from the `apis.services.mailer` logger — **monitor that logger**,
it is the only signal you get.

`EMAIL_TIMEOUT` is not optional. Django sets no socket timeout by default, so one
unreachable mail server would pin a gunicorn worker per request on an unauthenticated
endpoint.

Verify after deploy:

```sh
python manage.py shell -c "from django.core.mail import send_mail;   send_mail('test', 'test', None, ['you@yourdomain.tld'])"
```

### Migration

This release adds `apis/migrations/0073_account_profile_and_password_reset.py`:
three nullable/blank columns on `apis_userprofile` (`phone`, `birth_date`, `avatar_url`)
and the new `apis_passwordresetcode` table. Additive only — no backfill, no data
migration, and safe to run before the new code is live.

Old reset codes are deleted opportunistically on each user's next request, so the table
stays bounded without a cron job.
