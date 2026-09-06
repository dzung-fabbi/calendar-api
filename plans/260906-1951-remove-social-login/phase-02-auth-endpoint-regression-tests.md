# Phase 02 — Auth endpoint regression tests

**Priority:** P1 · **Status:** complete · **Effort:** 1h · **Blocked by:** phase 01

The project has **zero** tests touching `/auth/` today (grep for `auth/token|Application|
oauth2_provider` across `apis/`, `giapha/`, `djangopj/`, `testkit/` → nothing). Phase 01
swaps the implementation of the only login endpoint the product has, so this test module is
the guard that the swap is behaviour-preserving.

## Context links

- [plan.md](plan.md) · previous: [phase-01](phase-01-remove-social-wiring-and-token-shim.md)
- Runner: `./scripts/run-tests.sh` → `manage.py test --settings=djangopj.settings_test apis giapha`

## Key insights

- **File location decision: `giapha/tests/test_auth_token_endpoints.py`.** Reason: the
  runner's default labels are literally `apis giapha` (`scripts/run-tests.sh`, the
  `if [ "$#" -eq 0 ]; then set -- apis giapha; fi` block). A project-level
  `djangopj/tests/` module would need that script edited, and would silently *not run* for
  anyone invoking `manage.py test apis giapha` by hand. Putting it under `giapha/tests/`
  costs nothing and cannot be skipped. It imports no `apis` code, so the
  "giapha ⟂ apis share no imports" rule in `docs/system-architecture.md` is intact.
- **`Application.client_secret` is hashed on save** — `oauth2_provider/models.py:28-39`,
  `ClientSecretField.pre_save()` runs `make_password()` on any value that
  `identify_hasher()` does not recognise. The test MUST keep the plaintext in a local
  variable; reading `app.client_secret` back gives the hash and every request 401s. This is
  the single most likely way to waste an hour here.
- `settings_test.py` forces `PASSWORD_HASHERS = ['...MD5PasswordHasher']`, so both the user
  password and the client secret hash fast. No perf concern.
- `PKCE_REQUIRED` defaults to `True` in DOT 2.2.0 but applies to the authorization_code
  grant only — irrelevant for `grant_type=password`.
- `settings_test` sets `DJANGO_ALLOWED_HOSTS=testserver,localhost`, so Django's test client
  works without extra host config.

## Requirements

**Functional coverage matrix**

| # | Case | Expectation |
|---|---|---|
| 1 | `POST /auth/token`, **form-encoded**, `grant_type=password` | 200, body has `access_token`, `refresh_token`, `token_type=Bearer` |
| 2 | `POST /auth/token`, **JSON** body, same grant | 200, same shape — **the regression this phase exists for** |
| 3 | `POST /auth/token/` (trailing slash), form-encoded | 200 |
| 4 | `POST /auth/token`, wrong password | 400, `error == "invalid_grant"` |
| 5 | `POST /auth/token`, `grant_type=refresh_token` (JSON) | 200, new `access_token` |
| 6 | `GET /api/gia-pha/clans` with `Authorization: Bearer <issued token>` | not 401 (200) — proves the trimmed `DEFAULT_AUTHENTICATION_CLASSES` still authenticates |
| 7 | `POST /auth/revoke-token` (JSON, valid) then reuse of the token | 204, then the Bearer request 401s |
| 8 | `POST /auth/revoke-token` missing `client_secret` | 400 with DRF field-error dict (shape preserved from `RevokeTokenSerializer`) |
| 9 | `POST /auth/convert-token`, `GET /auth/login/facebook/`, `GET /auth/login/google-oauth2/`, `GET /auth/complete/facebook/`, `POST /auth/invalidate-sessions`, `GET /auth/authorize` | **404 each** — proves the social surface is gone |

**Non-functional**
- Uses only `django.test.TestCase` + `self.client`; no new test helper, no factory changes
  (DRY — `giapha/tests/factories.py` has no user/OAuth helper worth extending for 1 module).
- 13 tests total (9 core cases + 4 error-path hardening tests):
  - Added `test_token_accepts_every_accept_header` (pinned Accept: text/html parity)
  - Added `test_token_multipart_body` (Django test client default case)
  - Added `test_token_non_object_json_body_is_400_not_500` (array/string/number JSON bodies)
  - Added `test_token_bad_client_secret_is_401_with_www_authenticate` (RFC 6749 §5.2 header)
  - Modified `test_token_form_encoded_body` to explicitly send urlencode, not multipart
- Module ≤ ~200 lines.

## Architecture

```
setUpTestData:
  user  = User.objects.create_user(username='tokentest', password=RAW_PASSWORD)
  RAW_SECRET = 'test-client-secret'
  app = Application.objects.create(
      name='test-client', user=user,
      client_type=Application.CLIENT_CONFIDENTIAL,
      authorization_grant_type=Application.GRANT_PASSWORD,
      client_secret=RAW_SECRET,          # hashed by pre_save -- keep RAW_SECRET around
  )
  cls.client_id = app.client_id          # NOT hashed, safe to read back
```

Helper on the TestCase:

```python
def _token(self, *, json_body=False, url='/auth/token', **overrides):
    payload = {
        'grant_type': 'password',
        'username': 'tokentest',
        'password': RAW_PASSWORD,
        'client_id': self.client_id,
        'client_secret': RAW_SECRET,
    }
    payload.update(overrides)
    if json_body:
        return self.client.post(url, data=payload, content_type='application/json')
    return self.client.post(url, data=payload)   # form-encoded by default
```

## Related code files

**Create**: `giapha/tests/test_auth_token_endpoints.py`
**Modify**: none. **Delete**: none.

## Implementation steps

1. Create the module with a single `class AuthTokenEndpointTests(TestCase)` and
   `setUpTestData` as sketched above.
2. Write cases 1-5 using `_token()`; assert on `response.json()` keys, not exact values.
3. Case 6: issue a token, then
   `self.client.get('/api/gia-pha/clans', HTTP_AUTHORIZATION=f'Bearer {tok}')`; assert
   `status_code != 401` (assert `== 200`, and add the 401 case without a header as the
   contrast).
4. Cases 7-8: `POST /auth/revoke-token` with `{client_id, client_secret, token}` as JSON;
   assert 204; then re-issue the Bearer request from case 6 and assert 401. Second test:
   drop `client_secret`, assert 400 and `'client_secret' in response.json()`.
5. Case 9: loop the six dead paths in a subTest, assert 404 on each.
6. Run `./scripts/run-tests.sh giapha.tests.test_auth_token_endpoints -v 2`, then the full
   `./scripts/run-tests.sh`.

## Todo list

- [x] Create `giapha/tests/test_auth_token_endpoints.py`
- [x] Cases 1-5 (token issuance: form, JSON, trailing slash, bad password, refresh)
- [x] Case 6 (Bearer still authenticates a real endpoint)
- [x] Cases 7-8 (revoke: success 204 + missing-field 400 shape)
- [x] Case 9 (six removed routes all 404)
- [x] 4 new error-path tests (Accept header, multipart, non-object JSON, WWW-Authenticate)
- [x] `./scripts/run-tests.sh` green for `apis giapha` together

## Success criteria

- All 13 tests pass in one `./scripts/run-tests.sh` run. **VERIFIED: 738 tests pass, 7 skipped.**
- Case 2: JSON bodies fail if replaced with `oauth2_provider.views.TokenView` (verified by
  temporarily swapping; confirmed result: `400 unsupported_grant_type`). Pins the JSON requirement.
- No change in the pass/fail state of any pre-existing test.

## Risk assessment

| Risk | L×I | Mitigation |
|---|---|---|
| Test written against `app.client_secret` (the hash) → everything 401s | High×Low | Called out above; keep `RAW_SECRET` as a module constant. |
| New tests perturb `auth_user` AUTO_INCREMENT and break an ordering-sensitive test in `apis` | Low×Med | The runner already runs both apps together on purpose; the full-suite run in step 6 is the check. `TestCase` rolls back per test. |
| `GET /api/gia-pha/clans` requires clan setup and 404s instead of 200 | Low×Low | Read `giapha/views/clan.py` first; if it is not a plain authenticated list, substitute another `IsAuthenticated`-only route (e.g. `POST /api/gia-pha/devices`) — the assertion only needs "not 401". |
| Case 9 passes for the wrong reason (typo'd URL always 404s) | Low×Med | Include one *live* URL (`/auth/token` with GET → 405, not 404) in the same subTest loop as a control. |

## Security considerations

- Test-only credentials, no real secrets. Do not copy the client secret pattern into
  fixtures that ship.
- Case 7 (revocation actually invalidates) is a security assertion, not just a smoke test —
  keep it.

## Rollback

Delete the test module. No production code touched.

## Next steps

Unblocks phase 04. Independent of phase 03 (disjoint files) — can run in parallel with it.
