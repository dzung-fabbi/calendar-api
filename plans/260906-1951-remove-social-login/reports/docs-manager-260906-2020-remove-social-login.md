# Docs Manager — Phase 04 Report

**Status:** DONE

## Files Updated

1. **`docs/api-reference.md`** (Vietnamese)
   - Lines 12–21: Rewrote auth section
   - Removed references to `drf_social_oauth2.urls`, `/auth/convert-token`, `/auth/login/{provider}/`
   - Added table with only `POST /auth/token` (grant `password` + `refresh_token`) and `POST /auth/revoke-token`
   - Added note: both form-encoded and JSON body formats accepted
   - Added note: removed endpoints now return 404; social login no longer supported (Vietnamese: "Đăng nhập Facebook/Google không còn được hỗ trợ")

2. **`docs/system-architecture.md`**
   - Line 5: Changed "OAuth2 / social auth" to "OAuth2 (django-oauth-toolkit, `grant_type=password`)"
   - Added reference to `djangopj/auth_token_views.py` (DRF shim module) in directory structure section
   - Noted rationale: django-oauth-toolkit views are form-encoded only

3. **`docs/codebase-summary.md`**
   - Added "auth endpoints" table in giapha section (lines 31–36)
   - Listed `/auth/token` and `/auth/revoke-token` routes, auth types, query counts
   - Noted both content-type formats
   - Kept `google-auth` / FCM lines untouched (they describe push, not login)

4. **`docs/deployment-guide.md`**
   - Added "Upgrading: social login removal" section (lines 219–279)
   - Step-by-step: backup (mysqldump), rebuild image, migrate, env cleanup, smoke test
   - Documented orphaned-account problem: users with social-only sign-in have unusable passwords
   - Provided SQL query to export affected accounts (with PII warning)
   - Listed recovery paths: admin-set password, password reset, re-registration
   - Post-migration verification SQL

## Style & Language

- Matched each file's existing tone and language:
  - `api-reference.md`: Vietnamese throughout
  - Other files: English (existing standard)
- Concise, no padding — DRY principle (plan folder is the history)
- No changelog created — none existed in `docs/`

## Unresolved Questions

- None. Spec fully satisfied.

**Summary:** Four docs files updated. Social login removal is now fully documented for operators and API clients. All references to Facebook/Google auth have been removed or marked as removed. Deployment guide covers the destructive migration and account recovery.
