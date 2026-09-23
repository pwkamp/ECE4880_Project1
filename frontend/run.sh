#!/usr/bin/env bash
set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$FRONTEND_DIR/../backend" && pwd)"
COMPOSE_FILE="$BACKEND_DIR/compose.yaml"
ENV_FILE="$BACKEND_DIR/.env"

fail() {
  echo "frontend/run.sh: $*" >&2
  exit 1
}

env_value() {
  local key="$1"
  awk -F= -v key="$key" '
    $1 == key {
      value = substr($0, index($0, "=") + 1)
      sub(/\r$/, "", value)
      print value
      exit
    }
  ' "$ENV_FILE"
}

check_port_available() {
  local port="$1"
  if command -v ss >/dev/null 2>&1 && ss -H -ltn "sport = :$port" | grep -q .; then
    fail "TCP port $port is already in use"
  fi
}

[[ "$(uname -s)" == "Linux" ]] || fail "the containerized integration stack requires a native Linux host"
command -v docker >/dev/null 2>&1 || fail "Docker Engine is not installed"
docker compose version >/dev/null 2>&1 || fail "the Docker Compose plugin is not installed"
docker info >/dev/null 2>&1 || fail "Docker Engine is not running or is not accessible"
command -v curl >/dev/null 2>&1 || fail "curl is required for the backend health check"
[[ -f "$ENV_FILE" ]] || fail "run backend/run.sh first so $ENV_FILE is created"

project_name="$(env_value COMPOSE_PROJECT_NAME)"
backend_port="$(env_value BACKEND_PORT)"
frontend_port="$(env_value FRONTEND_PORT)"
email_mode="$(env_value EMAIL_MODE)"
project_name="${project_name:-ece4880-integration}"
backend_port="${backend_port:-8000}"
frontend_port="${frontend_port:-5173}"
if [[ "$email_mode" == "live" ]]; then
  [[ -n "$(env_value SMTP_USER)" ]] || fail "EMAIL_MODE=live requires SMTP_USER in backend/.env"
  [[ -n "$(env_value SMTP_PASS)" ]] || fail "EMAIL_MODE=live requires SMTP_PASS in backend/.env"
fi

# Linux always reaches FastAPI through Vite's same-origin proxy.
export VITE_BLE_API_BASE=""
compose=(docker compose --profile linux --project-name "$project_name" --env-file "$ENV_FILE" --file "$COMPOSE_FILE")
"${compose[@]}" config --quiet
backend_container="$("${compose[@]}" ps --quiet backend)"
[[ -n "$backend_container" ]] || fail "the backend is not running; start backend/run.sh first"
[[ "$(docker inspect --format '{{.State.Health.Status}}' "$backend_container" 2>/dev/null || true)" == "healthy" ]] || \
  fail "the backend container is not healthy; inspect its logs before starting the frontend"
curl --fail --silent --show-error "http://127.0.0.1:$backend_port/healthz" >/dev/null || \
  fail "the backend health endpoint is unreachable"
check_port_available "$frontend_port"

echo "Starting the web console on http://127.0.0.1:$frontend_port"
exec "${compose[@]}" up --build --no-deps frontend
