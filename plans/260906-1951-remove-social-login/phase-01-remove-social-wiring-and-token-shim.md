# Phase 01 — Remove social wiring + `/auth/token` compat shim

**Priority:** P1 (everything else blocks on it) · **Status:** complete · **Effort:** 1h

Rip `drf-social-oauth2` / `social-auth-*` out of settings, urls, requirements and env, and
replace the two token endpoints it provided with a ~70-line local DRF shim so shipped
clients see zero change.

## Context links

- Overview: [plan.md](plan.md)
- Next: [phase-02](phase-02-auth-endpoint-regression-tests.md) (tests), [phase-03](phase-03-drop-social-django-tables-migration.md) (migration)
- Rules: `~/.claude/rules/development-rules.md` (YAGNI/KISS/DRY, <200 lines/file)

## Key insights (verified against installed sources in `calendar-api-test:latest`)

1. `oauth2_provider/views/base.py:248-271` — `TokenView` is
   `@method_decorator(csrf_exempt, name="dispatch")` + `(OAuthLibMixin, View)`. Same for
   `RevokeTokenView` at `base.py:274-286`. **CSRF is already handled; no extra wrapping
   needed.** But they are plain Django `View`s reading `request.POST` →
   **`application/x-www-form-urlencoded` bodies ONLY**.
2. `drf_social_oauth2/views.py:50-83` — today's `/auth/token` is
   `(CsrfExemptMixin, OAuthLibMixin, APIView)`, `permission_classes = (AllowAny,)`, and its
   `post()` copies `request.data` into `request._request.POST` before
   `create_token_response()` → **a JSON body works today**. Same trick in its
   `RevokeTokenView` (`views.py:140-161`), which additionally validates with
   `RevokeTokenSerializer` (`serializers.py:25-28`: required `client_id`, `client_secret`,
   `token`) and returns **204** when oauthlib gives an empty body.
   ⇒ Mounting DOT's views raw would silently break every JSON client. Shim is mandatory.
3. `oauth2_provider/views/mixins.py:17-35` — `OAuthLibMixin.server_class` /
   `validator_class` / `oauthlib_backend_class` default to `None` and fall back to
   `oauth2_settings`. The shim does **not** need to set them (drf-social-oauth2 set them
   only because it swapped in `SocialTokenServer` for convert-token).
4. `drf_social_oauth2/backends.py:16-25` — `DjangoOAuth2` evaluates
   `reverse('drf:token')` **in the class body** (import time). Removing the URL include
   without removing this backend from `AUTHENTICATION_BACKENDS` = instant
   `NoReverseMatch` at startup. Both edits ship together.
5. `oauth2_provider/oauth2_validators.py:694-709` — `validate_user()` calls Django's
   `authenticate()`, which `ModelBackend` serves. Password grant does **not** need
   `DjangoOAuth2`; `ModelBackend` alone is sufficient.
6. Repo-wide grep for `facebook|social_auth|social_django|drf_social|social_core`
   (excluding `.git`, `plans/`, `docs/`) hits **only** `.env.example:24-27`,
   `djangopj/settings.py:59,60,91,92,158,197,199-201,204-212,235-238`,
   `djangopj/urls.py:24`, `docker-compose.yml:26-29`. **No app code imports these
   packages** — `apis/`, `giapha/`, `testkit/` are clean.

## Requirements

**Functional**
- `POST /auth/token` and `POST /auth/token/` accept form-encoded **and** JSON bodies,
  `grant_type=password`, return the same JSON token payload and status codes as today.
- `POST /auth/revoke-token[/]` behaves as today (400 field errors on missing
  `client_id`/`client_secret`/`token`; 204 on success).
- All other `/auth/*` routes 404.
- No import of `social_*` / `drf_social_oauth2` survives anywhere.

**Non-functional**
- Shim module ≤ ~80 lines, no social code, docstring states *why it exists* so nobody
  "simplifies" it back to raw DOT views.
- Bearer auth on existing endpoints unchanged (`OAuth2Authentication` stays default).

## Architecture / data flow

```
client (form OR json body)
  -> djangopj/urls.py  url(r'^auth/token/?$')
  -> djangopj.auth_token_views.TokenView (DRF APIView, csrf_exempt, AllowAny)
       request.data  --copy-->  request._request.POST      <- the whole point
  -> OAuthLibMixin.create_token_response(request._request)
  -> oauth2_settings.OAUTH2_VALIDATOR_CLASS.validate_user()
  -> django.contrib.auth.authenticate() -> ModelBackend    <- only backend left
  -> DOT AccessToken/RefreshToken rows (oauth2_provider tables, untouched)
  <- Response(json)
```

## Related code files

**Create**
- `djangopj/auth_token_views.py`

**Modify**
- `djangopj/settings.py` — L59-60, L91-92, L158, L196-215, L235-240
- `djangopj/urls.py` — L24
- `requirements.txt`
- `docker-compose.yml` — L26-29
- `.env.example` — L24-28 (the `# --- Social auth ---` block incl. its heading)

**Delete**: none.

## Implementation steps

1. **Create `djangopj/auth_token_views.py`.** Reference implementation (adjust only if a
   read of the installed source contradicts it):

```python
"""Local drop-in replacement for drf-social-oauth2's token endpoints.

WHY THIS EXISTS -- do not "simplify" it into `oauth2_provider.views.TokenView`.
`/auth/token` and `/auth/revoke-token` used to come from `drf_social_oauth2.urls`.
That package was removed together with Facebook/Google login, but shipped mobile
clients still call both URLs and some of them send a JSON body. django-oauth-toolkit's
own views are plain Django `View`s that read `request.POST`, i.e. form-encoded
bodies only; drf-social-oauth2's were DRF `APIView`s that copied `request.data`
into `request._request.POST` first. This module keeps that behaviour (and the
optional trailing slash, handled in djangopj/urls.py) with zero social code.
"""
from json import loads as json_loads

from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from oauth2_provider.models import AccessToken
from oauth2_provider.views.mixins import OAuthLibMixin
from rest_framework.fields import CharField
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from rest_framework.exceptions import ParseError


def _copy_parsed_body_into_post(request, data):
    """Expose DRF's parsed body as `request.POST` so oauthlib can read it.

    DRF has already consumed the request stream by the time DOT looks at
    `request.POST`; without this copy a JSON body arrives as an empty POST dict
    and every JSON client gets `unsupported_grant_type`.

    If data is not a mapping (e.g. a list, string, number), raise ParseError so
    non-object JSON bodies return 400 instead of 500 on an unauthenticated endpoint.

    NOTE: request._request.POST is left _mutable=True and now carries plaintext
    passwords. Any request-logging middleware added later would see them; use with
    @sensitive_variables if added.
    """
    if not isinstance(data, dict):
        raise ParseError('Request body must be a JSON object.')
    request._request.POST = request._request.POST.copy()
    for key, value in data.items():
        request._request.POST[key] = value


def _with_oauthlib_headers(response, headers):
    """Copy oauthlib's response headers (e.g. WWW-Authenticate) onto the DRF response.

    oauthlib includes RFC 6749 §5.2 WWW-Authenticate on 401s; DRF's Response wouldn't
    unless we copy them. Never clobber Content-Type (oauthlib may set it; DRF's
    JSONRenderer will override anyway).
    """
    for key, value in headers.items():
        if key.lower() != 'content-type':
            response[key] = value
    return response


@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class TokenView(OAuthLibMixin, APIView):
    """`POST /auth/token` -- OAuth2 password / refresh_token grant.

    csrf_exempt is already applied by DRF's APIView.as_view().
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()   # client credentials live in the body, not a Bearer header

    @sensitive_variables('password')
    def post(self, request, *args, **kwargs):
        _copy_parsed_body_into_post(request, request.data)
        try:
            url, headers, body, status = self.create_token_response(request._request)
        except AccessToken.DoesNotExist:
            return Response(
                data={'invalid_grant': 'The access token of your Refresh Token does not exist.'},
                status=HTTP_400_BAD_REQUEST,
            )
        response = Response(data=json_loads(body), status=status)
        return _with_oauthlib_headers(response, headers)


class _RevokeTokenSerializer(Serializer):
    """Mirrors drf_social_oauth2.serializers.RevokeTokenSerializer field-for-field so
    the 400 error shape clients already parse does not change."""

    client_id = CharField(max_length=100)
    client_secret = CharField(max_length=255)
    token = CharField(max_length=500)


class RevokeTokenView(OAuthLibMixin, APIView):
    """`POST /auth/revoke-token` -- logout.

    csrf_exempt is already applied by DRF's APIView.as_view().
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @sensitive_variables('client_secret')
    def post(self, request, *args, **kwargs):
        serializer = _RevokeTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _copy_parsed_body_into_post(request, serializer.validated_data)
        url, headers, body, status = self.create_revocation_response(request._request)
        response = Response(data=json_loads(body) if body else '', status=status if body else 204)
        return _with_oauthlib_headers(response, headers)
```

2. **`djangopj/urls.py`** — drop the `drf_social_oauth2` include, add two explicit routes.
   Do **not** `include('oauth2_provider.urls')` (would expose `/auth/applications/`,
   `/auth/authorize/`, `/auth/introspect/` — YAGNI, and an auth-surface increase):

```python
from djangopj.auth_token_views import RevokeTokenView, TokenView
...
    url(r'^auth/token/?$', TokenView.as_view(), name='auth-token'),
    url(r'^auth/revoke-token/?$', RevokeTokenView.as_view(), name='auth-revoke-token'),
```

   The `?$` keeps the optional trailing slash drf-social-oauth2 had. No `namespace`
   (nothing reverses these URLs).

3. **`djangopj/settings.py`** — delete, in this order:
   - `INSTALLED_APPS`: `'social_django'`, `'drf_social_oauth2'` (L59-60). **Keep
     `'oauth2_provider'`.**
   - `TEMPLATES` context processors: both `social_django.context_processors.*` (L91-92).
   - `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`: drop
     `'drf_social_oauth2.authentication.SocialAuthentication'` (L158). Leaves a 1-tuple —
     keep the trailing comma.
   - `AUTHENTICATION_BACKENDS` (L196-202) → `('django.contrib.auth.backends.ModelBackend',)`.
   - Delete L204-215 (Facebook/Google key/secret/scope) and L235-240
     (`SOCIAL_AUTH_FACEBOOK_SCOPE`, `SOCIAL_AUTH_FACEBOOK_PROFILE_EXTRA_PARAMS`).
   - **KEEP** L217-233 (`FIREBASE_*`, `S3_*`) untouched.
4. **`requirements.txt`** — remove `drf-social-oauth2==2.1.1`,
   `social-auth-app-django==5.1.0`, `social-auth-core==4.4.2`, plus the three
   social-auth-core-only transitives `python3-openid==3.2.0`, `defusedxml==0.7.1`,
   `requests-oauthlib==1.3.1`. Before deleting the transitives run
   `grep -rn "openid\|defusedxml\|requests_oauthlib" --include=*.py .` → must be empty.
   **KEEP** `django-oauth-toolkit`, `oauthlib`, `jwcrypto`, `PyJWT`, `cryptography`,
   `requests`, `google-auth`, `rsa`, `pyasn1`, `python-jose`, `ecdsa`.
5. **`docker-compose.yml`** — delete L26-29 (the four `SOCIAL_AUTH_*` passthroughs).
6. **`.env.example`** — delete the `# --- Social auth ---` heading and its four vars.
7. Rebuild + smoke: `docker compose build web` then
   `docker compose run --rm web python manage.py check`.

## Todo list

- [x] Create `djangopj/auth_token_views.py`
- [x] Rewrite `/auth/` routes in `djangopj/urls.py`
- [x] Strip social entries from `djangopj/settings.py` (6 edits)
- [x] Prune `requirements.txt` (6 pins) after the import grep comes back empty
- [x] Strip `SOCIAL_AUTH_*` from `docker-compose.yml` and `.env.example`
- [x] `docker compose build web && docker compose run --rm web python manage.py check` → clean

## Success criteria

- `manage.py check` exits 0 with `social_django`/`drf_social_oauth2` gone from INSTALLED_APPS.
- `grep -rniE "facebook|social_auth|social_django|drf_social|social_core" --exclude-dir=.git --exclude-dir=plans --exclude-dir=docs .` → **zero hits**.
- Rebuilt image has no social package:
  `docker compose run --rm web pip list | grep -iE "social|openid"` → empty.
- Phase 02's tests pass (that is the real proof; this phase alone is unverified).

## Risk assessment

| Risk | L×I | Mitigation |
|---|---|---|
| JSON clients break because DOT views are form-only | High×High | The shim — this phase's whole reason to exist. Pinned by phase 02 tests. |
| `NoReverseMatch` at import: `DjangoOAuth2` reverses `drf:token` in its class body | Med×High | Remove backend + URL include in the SAME commit; `manage.py check` catches it immediately. |
| Removing a transitive something else needs | Med×Med | Import grep before removal + full image rebuild + `./scripts/run-tests.sh`. Fallback: restore the 3 transitive pins, harmless when unused. |
| Non-object JSON body (array, string, number) → 500 on unauthenticated endpoint | Med×Med | `_copy_parsed_body_into_post` raises `ParseError` → 400. Pinned by tests. |
| `authentication_classes = ()` differs from today (defaults ran) | Low×Low | Deliberately more permissive: stale/invalid `Bearer` on refresh can no longer 401. Nothing that worked stops working. |
| Admin pages for DOT `Application`/`AccessToken` reverse `oauth2_provider:*` | Low×Med | **Unchanged from today** — project never included `oauth2_provider.urls` (only `drf_social_oauth2.urls`, namespace `drfso2`). Spot-check `/admin/oauth2_provider/application/` after deploy. |
| Password/secrets in error frames without `@sensitive_variables` | Low×Low | Covered: both `@sensitive_post_parameters` on dispatch and `@sensitive_variables` on methods. |

## Security considerations

- Attack surface **shrinks**: convert-token, authorize, disconnect-backend, session
  invalidation and the social redirect flow all disappear.
- `permission_classes = (AllowAny,)` on the token endpoint is correct and matches today;
  authorisation is the client_id/client_secret + user credentials in the body.
- `sensitive_post_parameters('password')` added (DOT has it, drf-social-oauth2 did not) →
  passwords stop appearing in Django error reports.
- Two FB/Google secrets stop being injected into the container. Rotate/delete them at the
  provider and in the deployment secret store (phase 04 documents this).

## Rollback

`git revert` the single commit, `docker compose build web`, redeploy. No data touched in
this phase — fully reversible.

## Next steps

Phase 02 (tests) and phase 03 (migration) unblock once this lands.
