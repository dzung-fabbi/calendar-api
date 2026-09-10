#!/bin/sh
# Run the test suite against the docker-compose MySQL service.
#
# Usage: ./scripts/run-tests.sh [extra manage.py test args]
#   e.g. ./scripts/run-tests.sh apis.tests.test_api_snapshots -v 2
#   e.g. ./scripts/run-tests.sh giapha.tests.test_query_counts -v 2
#
# With NO args, runs both apps in one invocation (`apis giapha`) -- phase 10's
# headline success criterion is that they pass together, not just separately
# (a shared table's AUTO_INCREMENT state, e.g. `auth_user`, can make one
# app's tests order-dependent on the other's). Any arg given on the command
# line is passed through UNCHANGED instead (positional test labels, `-v 2`,
# `--keep-test-db`, ...) -- so `./scripts/run-tests.sh giapha.tests.test_x`
# still runs exactly that, never `apis giapha giapha.tests.test_x`.
set -e

# Git Bash on Windows rewrites /code into a host path; stop it.
export MSYS_NO_PATHCONV=1

SCRIPT_DIR=$(cd "$(dirname "$0")/.." && pwd)
# Docker on Windows needs a native path (C:/...), which `pwd -W` provides.
PROJECT_DIR=$(cd "$SCRIPT_DIR" && { pwd -W 2>/dev/null || pwd; })

docker compose up -d db >/dev/null 2>&1

# Ask the running `db` container which network it is on instead of guessing
# the compose project name: it is derived from the checkout directory (this
# repo has lived as both `calendar-api` and `calendar`), so a hard-coded
# `calendar-api_default` silently yields an empty --network on other clones.
NETWORK=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' "$(docker compose ps -q db)")
docker build -q -f "$PROJECT_DIR/Dockerfile.test" -t calendar-api-test:latest "$PROJECT_DIR" >/dev/null

# Default test labels when the caller passes none at all. `$#` (not `$@`)
# is what to check here: an empty-but-present arg (`./run-tests.sh ""`)
# must still count as "an arg was given" and be passed through as-is.
if [ "$#" -eq 0 ]; then
    set -- apis giapha
fi

exec docker run --rm \
    --network "$NETWORK" \
    -v "$PROJECT_DIR:/code" \
    -w /code \
    -e DB_HOST=db \
    -e REWRITE_SNAPSHOTS="${REWRITE_SNAPSHOTS:-}" \
    calendar-api-test:latest \
    python manage.py test --settings=djangopj.settings_test "$@"
