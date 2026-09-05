#!/bin/sh
# Run the test suite against the docker-compose MySQL service.
#
# Usage: ./scripts/run-tests.sh [extra manage.py test args]
#   e.g. ./scripts/run-tests.sh apis.tests.test_api_snapshots -v 2
set -e

# Git Bash on Windows rewrites /code into a host path; stop it.
export MSYS_NO_PATHCONV=1

SCRIPT_DIR=$(cd "$(dirname "$0")/.." && pwd)
# Docker on Windows needs a native path (C:/...), which `pwd -W` provides.
PROJECT_DIR=$(cd "$SCRIPT_DIR" && { pwd -W 2>/dev/null || pwd; })

NETWORK=$(docker network ls --format '{{.Name}}' | grep -E '^calendar-api[_-]default$' | head -1)

docker compose up -d db >/dev/null 2>&1
docker build -q -f "$PROJECT_DIR/Dockerfile.test" -t calendar-api-test:latest "$PROJECT_DIR" >/dev/null

exec docker run --rm \
    --network "$NETWORK" \
    -v "$PROJECT_DIR:/code" \
    -w /code \
    -e DB_HOST=db \
    -e REWRITE_SNAPSHOTS="${REWRITE_SNAPSHOTS:-}" \
    calendar-api-test:latest \
    python manage.py test --settings=djangopj.settings_test "$@"
