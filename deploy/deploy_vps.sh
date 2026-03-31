#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/japonica-crm}"
BRANCH="${BRANCH:-main}"
COMPOSE_BASE="${COMPOSE_BASE:-docker-compose.yml}"
COMPOSE_VPS="${COMPOSE_VPS:-deploy/docker-compose.vps.yml}"

cd "$APP_DIR"

git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

docker compose -f "$COMPOSE_BASE" -f "$COMPOSE_VPS" config >/dev/null
docker compose -f "$COMPOSE_BASE" -f "$COMPOSE_VPS" up -d --force-recreate
