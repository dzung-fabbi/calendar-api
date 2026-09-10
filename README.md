# calendar-api

Vietnamese almanac (`apis/`) and family genealogy (`giapha/`) backend, built on Django 3.1
and MySQL 5.7. See `docs/` for system architecture, deployment, and codebase standards.

API reference (Vietnamese) for JWT login (`/api/auth/login`), the `apis/` endpoints (accounts, file upload,
almanac, booking), 26 clan endpoints, and 13 personal family tree endpoints (`/api/gia-pha/v1/family/`): `docs/api-reference.md`.

## Local development

```bash
docker-compose up -d    # Start services
docker-compose down     # Stop and remove containers
```
