# Phase 02 — `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout`

**Priority:** P1 · **Status:** completed · **Effort:** 1h · **Blocked by:** phase 01

## Context links

- [plan.md](plan.md) · previous: [phase-01](phase-01-token-core-model-services-authentication.md)
  · next: [phase-03](phase-03-remove-django-oauth-toolkit.md)
- Pattern to copy: `apis/views/auth_register.py` (throttle scope + `authentication_classes = ()`)
- Deleted in this phase: `djangopj/auth_token_views.py` (145 lines) and its two `url()` routes

## Overview

Three thin views over phase 01's selectors, mounted inside `apis/urls.py` next to the other
`auth/*` routes. The root-level `/auth/token` and `/auth/revoke-token` disappear with the
module that served them.

## Key insights

- **`AuthenticationFailed` raised from a view with `authentication_classes = ()` returns 403,
  not 401.** DRF's `APIView.handle_exception` downgrades the status when
  `get_authenticate_header()` is empty, and it is empty precisely because there are no
  authenticators. These three views must therefore `return Response(..., status=401)`
  explicitly. This is the single most likely bug in the phase.
- `authentication_classes = ()` is required for all three: a caller holding a stale/expired
  Bearer header must still be able to log in, refresh or log out — the same reason
  `auth_token_views.TokenView` had it (and `auth_register.py` still does).
- `sensitive_post_parameters('password')` must decorate **`dispatch`**, not `post`: the
  decorator asserts it got a real `HttpRequest`, and DRF hands `post` its own wrapper.
- Only login needs it — `refresh` and `logout` carry an opaque token, and adding the
  decorator for `refresh_token` would be cargo cult. (It is still never logged: nothing in
  the request path logs bodies.)
- The response is deliberately **not** `{"data": ...}`-wrapped. `docs/api-reference.md`
  already lists envelope exceptions; phase 05 adds these three.
- `logout` answers **204 with a genuinely empty body**, not the old `""` two-byte oddity.
  New endpoint, no client depends on the old quirk.
- `authenticate()` does not update `last_login` — and neither did the OAuth2 password grant
  (oauthlib called `authenticate()` too). Behaviour is unchanged on purpose; do not add
  `update_last_login` here without deciding it as a separate change.

## Requirements

**Functional**
- `POST /api/auth/login {username, password}` → 200 token payload. Missing field → 400 field
  errors. Wrong password, unknown user, inactive user → **401**, one identical body.
- `POST /api/auth/refresh {refresh_token}` → 200 with a **new** pair; the presented token is
  gone. Unknown / expired / already-used token → 401, one identical body.
- `POST /api/auth/logout {refresh_token}` → **204** whether or not the row existed.
- All three: `AllowAny`, no authenticator, form-encoded **and** JSON bodies both work (DRF's
  default parsers already cover this — no shim needed, unlike the DOT views).

**Non-functional**
- `apis/views/auth_login.py` < 200 lines, three classes.
- Throttle scopes `auth-login` (20/hour) and `auth-refresh` (60/hour), per-IP, with the same
  `NUM_PROXIES` caveat already written above `DEFAULT_THROTTLE_RATES`.

## Architecture

```
POST /api/auth/login
  serializers.auth.LoginSerializer            -> 400 on missing fields
  django.contrib.auth.authenticate()          -> None => 401 generic
  selectors.refresh_tokens.issue_token_pair() -> INSERT one row
  200 {access_token, refresh_token, token_type, expires_in}

POST /api/auth/refresh
  serializers.auth.RefreshTokenSerializer
  selectors.refresh_tokens.consume_refresh_token()   -> DELETE old row (rowcount-checked)
  issue_token_pair()                                 -> INSERT new row
  200 same shape  |  401 generic

POST /api/auth/logout
  selectors.refresh_tokens.delete_refresh_token()    -> DELETE (0 rows is fine)
  204 no body
```

## Related code files

**Create**
- `apis/views/auth_login.py` — `LoginAPIView`, `RefreshTokenAPIView`, `LogoutAPIView`

**Modify**
- `apis/serializers/auth.py` (148 lines → ~175) — add `LoginSerializer`, `RefreshTokenSerializer`
- `apis/views/__init__.py` — import + `__all__`
- `apis/urls.py` — three `path()`s; **rewrite** the stale comment at L49-51 that says login
  lives at the root
- `djangopj/urls.py` — delete both `url()` lines, the `from djangopj.auth_token_views import ...`
  line, and the now-unused `from django.conf.urls import url` import
- `djangopj/settings.py` — `auth-login`/`auth-refresh` entries in `DEFAULT_THROTTLE_RATES`

**Delete**
- `djangopj/auth_token_views.py`

## Implementation steps

1. **Serializers** in `apis/serializers/auth.py` (module docstring already explains why these
   are plain `Serializer`s):

```python
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)      # write_only: never echoed

class RefreshTokenSerializer(serializers.Serializer):
    # 43 chars for token_urlsafe(32); the cap only bounds junk input.
    refresh_token = serializers.CharField(max_length=255, write_only=True)
```
   Add the two Vietnamese constants next to `EMAIL_TAKEN`:
   `INVALID_CREDENTIALS = 'Tên đăng nhập hoặc mật khẩu không đúng.'`
   `INVALID_REFRESH_TOKEN = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'`

2. **`apis/views/auth_login.py`.** Module docstring must state the three facts that are
   otherwise re-discovered the hard way: (a) 401 is `Response(...)`, never
   `raise AuthenticationFailed` — see Key insights; (b) `authentication_classes = ()` is
   deliberate; (c) the payload is unwrapped on purpose.

```python
@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = ()
    throttle_scope = 'auth-login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = authenticate(request=request, **serializer.validated_data)
        if user is None:
            # ModelBackend already returns None for an inactive user, so a
            # disabled account and a wrong password are indistinguishable here
            # -- which is the point.
            return Response({'detail': INVALID_CREDENTIALS},
                            status=status.HTTP_401_UNAUTHORIZED)
        return Response(issue_token_pair(user))
```
   `RefreshTokenAPIView` mirrors it with `consume_refresh_token` and `INVALID_REFRESH_TOKEN`.
   `LogoutAPIView` validates, calls `delete_refresh_token`, returns
   `Response(status=status.HTTP_204_NO_CONTENT)` — no throttle scope (a 256-bit token is not
   guessable and the call is one indexed DELETE); say so in a comment so the omission reads
   as a decision.

3. `apis/views/__init__.py`: add the three names, keep the list alphabetical.

4. `apis/urls.py`: add inside the existing "Account management" group and replace its comment:

```python
    path("auth/login", LoginAPIView.as_view(), name="auth-login"),
    path("auth/refresh", RefreshAPIView.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutAPIView.as_view(), name="auth-logout"),
```
   No trailing-slash variants: the old optional slash existed for shipped clients of a URL
   that no longer exists. New clients use these paths exactly, like every other `apis/` route.

5. `djangopj/urls.py`: remove the import of `RevokeTokenView, TokenView`, both `url()` entries,
   and `from django.conf.urls import url` (nothing else uses it — verify with grep). The
   remaining file is three `path()`s.

6. `git rm djangopj/auth_token_views.py`.

7. `djangopj/settings.py` — inside `DEFAULT_THROTTLE_RATES`, next to the other `auth-*` scopes:

```python
        # Login and refresh (`apis/views/auth_login.py`). Unauthenticated, so
        # per-IP, with the NUM_PROXIES caveat above: this raises the cost of
        # single-source credential stuffing and nothing more. `/auth/token` had
        # NO limit at all, so this is strictly an improvement.
        'auth-login': '20/hour',
        'auth-refresh': '60/hour',
```

8. Smoke by hand before phase 03 (the suite is red until phase 04):
   `curl -X POST .../api/auth/login -d 'username=…&password=…'` → 200 with four keys;
   the `access_token` on `GET /api/me` → 200; refresh → new pair, old refresh → 401;
   logout → 204, then refresh → 401.

## Todo list

- [x] `LoginSerializer` + `RefreshTokenSerializer` + the two message constants
- [x] `apis/views/auth_login.py` (three views, 401 via `Response`, not `raise`)
- [x] `apis/views/__init__.py` exports
- [x] `apis/urls.py` routes + stale comment rewritten
- [x] `djangopj/urls.py` cleaned (routes, import, unused `url` import)
- [x] `djangopj/auth_token_views.py` deleted
- [x] `auth-login` / `auth-refresh` throttle rates
- [x] Manual curl round trip: login → me → refresh → logout → refresh 401

## Deviations from plan

1. **`sensitive_post_parameters` and `@sensitive_variables` decorators added**: Refresh and logout views now mask `refresh_token` in error reports; selector functions masked with `@sensitive_variables('raw')` to prevent raw tokens from leaking in exception tracebacks.
2. **Refresh operation wrapped in `transaction.atomic()`**: Ensures atomic consistency between token consumption and issuance (see phase 01 deviation).
3. **Pre-existing throttle bug fixed outside this phase**: Account views (register, forgot-password, verify-code, reset-password, change-password) all had `throttle_scope` set but were missing `throttle_classes = [ScopedRateThrottle]`. This made throttle rates silent no-ops in production. Now all six endpoints enforce real per-IP rate limits (register 5/h, forgot 5/h, verify 10/h, reset 5/h, change-password 10/h/user, login 20/h, refresh 60/h). This is a production behaviour change — requires monitoring and `DJANGO_NUM_PROXIES` verification.

## Success criteria

- [x] `grep -rn "auth/token\|revoke-token" --include=*.py .` matches only test files (phase 04
  fixes those) and docs (phase 05).
- [x] Login with the wrong password returns **401** (not 403 — the DRF downgrade trap) with body
  `{"detail": "..."}` and no field-level detail.
- [x] Both a form-encoded and a JSON login body succeed.
- [x] `GET /api/home` (public) still 200s with no `Authorization` header.

## Risk assessment

| Risk | L×I | Mitigation |
|---|---|---|
| `raise AuthenticationFailed` → 403 instead of 401 | **High**×High | Explicit `Response(..., 401)`; a phase 04 test asserts exactly 401 |
| `sensitive_post_parameters` on `post` → `AssertionError` at runtime | Med×High | `@method_decorator(..., name='dispatch')`, as in the deleted module |
| Removing `url()` leaves an unused import → flake noise / NameError | Med×Low | Grep `djangopj/urls.py` after the edit |
| Throttle bucket shared with `auth-register` by copy-paste | Low×Med | Distinct scope names; verify with a 21st login attempt returning 429 |
| A client still calling `/auth/token` gets a confusing 404 | **Certain**×Med | Accepted, announced; phase 05 documents the migration |

## Security considerations

- Uniform 401 body on login: no user enumeration, and an inactive account is indistinguishable
  from a wrong password (`ModelBackend.user_can_authenticate` already returns `None`).
- `sensitive_post_parameters('password')` keeps the password out of Django error reports.
- Refresh rotation means a stolen refresh token is single-use; the legitimate client's next
  refresh fails, which is the detectable signal. Detection/alerting is out of scope.
- Login is now throttled, which `/auth/token` never was — closes the gap recorded in
  `docs/deployment-guide.md` → "Known gap: `/auth/token` is unthrottled".

## Next steps

Phase 03 removes the package and its tables.
