#!/usr/bin/env bash
# Lightweight latency baseline for mentor review (NFR-P03).
# Requires: stack up, `hey` installed (go install github.com/rakyll/hey@latest)
#
# Usage:
#   ./scripts/load_baseline.sh
#   BASE=http://localhost:8000 ./scripts/load_baseline.sh

set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
EMAIL="${LOAD_EMAIL:-load-instructor@test.com}"
PASS="${LOAD_PASS:-secret123}"

echo "== SmartCourse load baseline =="
echo "API: $BASE"
echo

register() {
  curl -sf -X POST "$BASE/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"role\":\"instructor\"}" \
    >/dev/null 2>&1 || true
}

register
TOKEN=$(curl -sf -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$EMAIL&password=$PASS" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

AUTH="Authorization: Bearer $TOKEN"

COURSE=$(curl -sf -X POST "$BASE/api/v1/courses" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"title":"Load baseline course"}')
COURSE_ID=$(echo "$COURSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "1. GET /health (50 requests, 5 concurrent)"
hey -n 50 -c 5 "$BASE/health"

echo
echo "2. GET /api/v1/courses (50 requests, 5 concurrent)"
hey -n 50 -c 5 -H "$AUTH" "$BASE/api/v1/courses?limit=20"

echo
echo "3. GET /api/v1/admin/metrics/overview (30 requests, 3 concurrent)"
hey -n 30 -c 3 -H "$AUTH" "$BASE/api/v1/admin/metrics/overview"

echo
echo "Done. Record p95 from hey output in docs/LOAD_BASELINE.md"
echo "Course created for smoke: $COURSE_ID"
