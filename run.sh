#!/usr/bin/env bash
# Usage: ./run.sh [private|public]   (default private, the Agent Manager tab: 127.0.0.1:7462)
set -euo pipefail
cd "$(dirname "$0")"
MODE="${1:-private}"
case "$MODE" in
  private) PORT=7462; DB=data/trade-private.db ;;
  public)  PORT=7463; DB=data/trade-public.db ;;
  *) echo "mode must be private or public" >&2; exit 2 ;;
esac
export TRADE_MODE="$MODE" DATABASE_PATH="${DATABASE_PATH:-$DB}"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --proxy-headers --forwarded-allow-ips=127.0.0.1
