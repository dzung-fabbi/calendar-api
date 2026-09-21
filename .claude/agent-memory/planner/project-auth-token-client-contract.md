---
name: project-auth-token-client-contract
description: /auth/token and /auth/revoke-token are a frozen contract - shipped mobile clients cannot be changed, so URL, optional trailing slash and JSON-body tolerance must survive any auth refactor
metadata:
  type: project
---

`POST /auth/token` and `POST /auth/revoke-token` must keep working at exactly those URLs,
with the trailing slash OPTIONAL, accepting **both** form-encoded and JSON bodies.

**Why:** mobile clients are already shipped and cannot be updated in lockstep with the
server. The JSON tolerance is not a design choice anyone made — it was inherited from
`drf-social-oauth2`'s DRF `APIView` implementation, which copied `request.data` into
`request._request.POST`. django-oauth-toolkit's own `TokenView` is a plain Django `View`
and is **form-encoded only**, so swapping to it silently breaks every JSON client.

**How to apply:** any plan that touches `/auth/` must preserve all four properties (URL,
optional slash, form body, JSON body) and pin them with tests. Do not "simplify"
`djangopj/auth_token_views.py` into raw DOT views. Verify the module still exists before
citing it — it was introduced by plans/260906-1951-remove-social-login.

Related: [[project-social-login-removal]]
