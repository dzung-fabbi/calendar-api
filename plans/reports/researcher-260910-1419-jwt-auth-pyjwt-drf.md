# JWT Auth with PyJWT 2.6.0 & DRF 3.14 — Best-Practice Design Report

## 1. PyJWT 2.6.0 API

**`jwt.encode()` returns `str` (not bytes)** — key change in PyJWT 2.x.

```python
import jwt
from datetime import datetime, timezone, timedelta

payload = {
    "user_id": 123,
    "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
    "iat": datetime.now(tz=timezone.utc),
    "jti": uuid.uuid4().hex  # JWT ID, not validated by library; for revocation tracking
}
token = jwt.encode(payload, key, algorithm="HS256")  # Returns str
```

**`jwt.decode()` requires `algorithms=` explicitly:**
```python
jwt.decode(token, key, algorithms=["HS256"], leeway=10)  # leeway: int/float/timedelta
```

**Exception hierarchy:**
- `InvalidTokenError` (base)
  - `DecodeError` → `InvalidSignatureError`
  - `ExpiredSignatureError` (subclass of `InvalidTokenError`)
  - `InvalidAudienceError`, `InvalidIssuerError`, `ImmatureSignatureError`

**Key rotation:** Use dedicated `JWT_SIGNING_KEY` env var (not `SECRET_KEY`) — enables rotation without invalidating all tokens if secret compromised. If using `SECRET_KEY`, key rotation revokes all active tokens.

## 2. DRF 3.14 BaseAuthentication Subclass

```python
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "").split()
        if not auth or auth[0].lower() != "bearer":
            return None  # Let other auth schemes try
        if len(auth) != 2:
            raise AuthenticationFailed("Invalid token format")
        
        try:
            payload = jwt.decode(auth[1], settings.JWT_SIGNING_KEY, 
                                algorithms=["HS256"], options={"verify_exp": True})
            user = User.objects.get(pk=payload["user_id"])
            return (user, payload)
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token expired")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Invalid token")
    
    def authenticate_header(self, request):
        return 'Bearer realm="api"'  # Ensures 401 (not 403) for unauthenticated
```

**Critical:** `authenticate_header()` is required — without it, DRF returns 403 Forbidden instead of 401 Unauthorized on missing auth.

## 3. Stateless Token Revocation on Password Change

Bind JWT claim to hash of current password; invalidates all tokens on password change:

```python
import hashlib

def get_password_hash(user):
    """Hash first 16 chars of user.password hash for claim binding."""
    return hashlib.sha256(user.password.encode()).hexdigest()[:16]

# In encode:
payload = {"user_id": user.id, "pwd_hash": get_password_hash(user)}

# In decode (after user lookup):
if payload["pwd_hash"] != get_password_hash(user):
    raise AuthenticationFailed("Token revoked (password changed)")
if not user.is_active:
    raise AuthenticationFailed("User inactive")
```

## 4. Refresh Tokens — DB Model & Rotation

```python
from django.db import models
import secrets, hashlib

class RefreshToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_tokens")
    token_hash = models.CharField(max_length=64, unique=True)  # SHA256 hash
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    
    @classmethod
    def create(cls, user):
        plain = secrets.token_urlsafe(32)  # ~256-bit entropy
        token_hash = hashlib.sha256(plain.encode()).hexdigest()
        expires = datetime.now(tz=timezone.utc) + timedelta(days=30)
        cls.objects.create(user=user, token_hash=token_hash, expires_at=expires)
        return plain  # Return only once to client
```

**Hash at rest (recommend SHA256).** Rotation on use: issue new refresh, mark old as `revoked_at`. Password change: delete all user's refresh tokens (`RefreshToken.objects.filter(user=user).delete()`).

## 5. Recommended Token Lifetimes (Mobile App)

- **Access:** 1 hour (env-configurable via `JWT_ACCESS_EXPIRY_SECONDS`)
- **Refresh:** 30 days (env-configurable via `JWT_REFRESH_EXPIRY_SECONDS`)

Response shape:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

## 6. Login Endpoint Hardening

```python
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.throttling import ScopedRateThrottle

@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class LoginView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'  # Configure: 'login': '20/hour' in DEFAULT_THROTTLE_RATES
    authentication_classes = ()  # Disable auth for login endpoint
    permission_classes = ()
    
    def post(self, request):
        user = authenticate(username=request.data['username'], 
                          password=request.data['password'])
        if not user:
            return Response({"error": "Invalid credentials"}, status=401)  # Same error for both cases
        # Issue tokens...
```

**Key points:**
- `@method_decorator(sensitive_post_parameters())` on `dispatch` (not `post`) — filters from error logs
- `authentication_classes = ()` overrides global default, allows unauthenticated access
- `ScopedRateThrottle` with per-IP scope (unauthenticated users throttled by IP)
- Generic error "Invalid credentials" prevents user enumeration

## 7. Removing django-oauth-toolkit (OAuth2Provider 2.2.0)

Tables to drop (in order, FK dependencies):
- `oauth2_provider_refreshtoken` (FK → accesstoken)
- `oauth2_provider_accesstoken` (FK → application, user)
- `oauth2_provider_idtoken` (FK → application)
- `oauth2_provider_grant` (FK → application)
- `oauth2_provider_application` (FK → user)

Migration squash command:
```sql
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS oauth2_provider_refreshtoken;
DROP TABLE IF EXISTS oauth2_provider_accesstoken;
DROP TABLE IF EXISTS oauth2_provider_idtoken;
DROP TABLE IF EXISTS oauth2_provider_grant;
DROP TABLE IF EXISTS oauth2_provider_application;
SET FOREIGN_KEY_CHECKS = 1;
```

Also delete migration rows: `DELETE FROM django_migrations WHERE app='oauth2_provider'`.

## 8. Pitfalls

1. **`USE_TZ=True`** + stateless claims: Must use `datetime.now(tz=timezone.utc)`, not naive `datetime.now()`.
2. **PyJWT `exp` claim:** Must be int (UNIX timestamp) or timezone-aware datetime; naive datetimes cause silent conversion errors.
3. **`jwt.decode` requires `algorithms=`** explicitly — raises `TypeError` if omitted.
4. **Key rotation with `SECRET_KEY`:** Invalidates all active tokens. Use dedicated `JWT_SIGNING_KEY` env var instead.
5. **Missing `authenticate_header()`:** DRF returns 403 (not 401) for missing auth — breaks client retry logic.
6. **HS256 with weak key:** `SECRET_KEY` may be insufficient; prefer `secrets.token_urlsafe(32)` for dedicated key.

## Unresolved Questions

- What happens if refresh token is stolen and cloned? (Recommend: tie to request IP via middleware, or rotate on every use with explicit old-token invalidation)
- Should access token include user `is_active`, `is_staff` claims for caching, or always fetch from DB? (Recommend: avoid — signals for user updates infrequent; fetch on demand if needed)
- Does project's DRF config already have `DEFAULT_THROTTLE_RATES` scopes defined? (Check `settings.py` `REST_FRAMEWORK` dict)

## Sources

- [PyJWT 2.6.0 Usage Examples](https://pyjwt.readthedocs.io/en/2.6.0/usage.html)
- [DRF Authentication Guide](https://www.django-rest-framework.org/api-guide/authentication/)
- [DRF Throttling](https://www.django-rest-framework.org/api-guide/throttling/)
- [Django PasswordResetTokenGenerator Implementation](https://github.com/django/django/blob/main/django/contrib/auth/tokens.py)
- [Django OAuth Toolkit 2.2.0 Models](https://django-oauth-toolkit.readthedocs.io/en/2.2.0/models.html)
- [Python Secrets Module](https://docs.python.org/3/library/secrets.html)
- [Django sensitive_post_parameters Decorator](https://docs.djangoproject.com/en/2.2/_modules/django/views/decorators/debug/)
- [MySQL 5.7 Foreign Key Handling](https://alvinalexander.com/blog/post/mysql/drop-mysql-tables-in-any-order-foreign-keys/)
