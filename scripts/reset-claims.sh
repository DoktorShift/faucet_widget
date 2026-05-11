#!/usr/bin/env bash
# Clear rate-limit state so you can claim again during dev iteration.
# Production has ip_cooldown_hours=24 / daily_cap — this lets you bypass
# both for local testing without dropping the strict settings.
#
# Usage:
#   ./scripts/reset-claims.sh             # wipe everything
#   ./scripts/reset-claims.sh --soft      # only IP cooldowns, keep totals
#
# Safe to run while uvicorn is running — SQLite (WAL mode) handles it.

set -euo pipefail

cd "$(dirname "$0")/.."

DB="data/claims.sqlite"

if [[ ! -f "$DB" ]]; then
  echo "no database yet at $DB — nothing to reset."
  exit 0
fi

MODE="${1:-hard}"

case "$MODE" in
  --soft|soft)
    echo "Soft reset: clearing IP cooldowns + used nonces, keeping claim history."
    sqlite3 "$DB" "DELETE FROM used_nonces; DELETE FROM challenge_hits; DELETE FROM claims WHERE created_at > strftime('%s','now') - 86400;"
    ;;
  --hard|hard|"")
    echo "Hard reset: wiping all rate-limit state (claims, nonces, throttle log)."
    sqlite3 "$DB" "DELETE FROM claims; DELETE FROM used_nonces; DELETE FROM challenge_hits;"
    ;;
  *)
    echo "usage: $0 [--soft|--hard]" >&2
    exit 1
    ;;
esac

echo "✓ done."

# Quick sanity report
echo ""
echo "Current state:"
sqlite3 "$DB" "SELECT 'claims:        ' || COUNT(*) FROM claims; \
              SELECT 'nonces:        ' || COUNT(*) FROM used_nonces; \
              SELECT 'challenge_hits:' || ' ' || COUNT(*) FROM challenge_hits;" 2>/dev/null
