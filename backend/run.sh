#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$BACKEND_DIR/compose.yaml"
ENV_FILE="$BACKEND_DIR/.env"
ENV_EXAMPLE="$BACKEND_DIR/.env.example"
KEEP_DATABASE=false
if [[ "${1:-}" == "--keep-db" && "$#" -eq 1 ]]; then
  KEEP_DATABASE=true
elif [[ "$#" -ne 0 ]]; then
  echo "Usage: backend/run.sh [--keep-db]" >&2
  exit 2
fi

fail() {
  echo "backend/run.sh: $*" >&2
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

[[ "$(uname -s)" == "Linux" ]] || fail "the containerized BLE backend requires a native Linux host"
command -v docker >/dev/null 2>&1 || fail "Docker Engine is not installed"
docker compose version >/dev/null 2>&1 || fail "the Docker Compose plugin is not installed"
docker info >/dev/null 2>&1 || fail "Docker Engine is not running or is not accessible"
command -v bluetoothctl >/dev/null 2>&1 || fail "BlueZ bluetoothctl is not installed"
[[ -S /run/dbus/system_bus_socket ]] || fail "the system D-Bus socket is unavailable"

bluez_version="$(bluetoothctl --version | grep -oE '[0-9]+(\.[0-9]+)+' | head -n 1 || true)"
[[ -n "$bluez_version" ]] || fail "could not determine the installed BlueZ version"
if [[ "$(printf '%s\n%s\n' '5.55' "$bluez_version" | sort -V | head -n 1)" != "5.55" ]]; then
  fail "BlueZ 5.55 or newer is required (found $bluez_version)"
fi
bluetoothctl show | grep -q 'Powered: yes' || fail "no powered BlueZ Bluetooth controller was found"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Created $ENV_FILE from .env.example with local-development defaults."
fi

for key in COMPOSE_PROJECT_NAME MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD MYSQL_ROOT_PASSWORD; do
  [[ -n "$(env_value "$key")" ]] || fail "$key must be set in $ENV_FILE"
done
[[ "$(env_value MYSQL_DATABASE)" == "thermometer" ]] || \
  fail "MYSQL_DATABASE must remain thermometer because database/schema.sql owns that name"

project_name="$(env_value COMPOSE_PROJECT_NAME)"
backend_port="$(env_value BACKEND_PORT)"
mysql_host_port="$(env_value MYSQL_HOST_PORT)"
backend_port="${backend_port:-8000}"
mysql_host_port="${mysql_host_port:-3306}"
mkdir -p "$BACKEND_DIR/.runtime"
chmod 700 "$BACKEND_DIR/.runtime"

# Linux always reaches FastAPI through Vite's same-origin proxy.
export VITE_BLE_API_BASE=""
compose=(docker compose --profile linux --project-name "$project_name" --env-file "$ENV_FILE" --file "$COMPOSE_FILE")
"${compose[@]}" config --quiet

if [[ "$KEEP_DATABASE" == false ]]; then
  echo "Stopping the integration stack and deleting its MySQL volume..."
  "${compose[@]}" down --volumes --remove-orphans
else
  echo "Keeping the existing MySQL volume and its temperature history."
fi
check_port_available "$backend_port"
if [[ "$KEEP_DATABASE" == false ]]; then
  check_port_available "$mysql_host_port"
fi

echo "Starting a fresh MySQL database..."
"${compose[@]}" up --build --detach mysql

mysql_container="$("${compose[@]}" ps --quiet mysql)"
for _ in $(seq 1 60); do
  if [[ "$(docker inspect --format '{{.State.Health.Status}}' "$mysql_container" 2>/dev/null || true)" == "healthy" ]]; then
    break
  fi
  sleep 1
done
[[ "$(docker inspect --format '{{.State.Health.Status}}' "$mysql_container" 2>/dev/null || true)" == "healthy" ]] || {
  "${compose[@]}" logs mysql
  fail "MySQL did not become healthy"
}

initial_count="$(
  "${compose[@]}" exec -T mysql sh -c \
    'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -N -e "SELECT COUNT(*) FROM temperature_samples"' \
    | tr -d '[:space:]'
)"
if [[ "$KEEP_DATABASE" == false ]]; then
  [[ "$initial_count" == "0" ]] || fail "fresh MySQL schema unexpectedly contains $initial_count temperature rows"
  echo "Fresh MySQL schema verified: temperature_samples contains 0 rows."
else
  echo "Existing MySQL schema verified: temperature_samples contains $initial_count rows."
fi

echo "MySQL is healthy. Starting the BLE backend on http://127.0.0.1:$backend_port"
exec "${compose[@]}" up --build backend
