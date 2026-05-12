#!/bin/sh
# value4value container entrypoint.
#
# Catches the two most common deploy mistakes BEFORE uvicorn starts so the
# operator gets a one-line remediation instead of a cryptic stack trace:
#
#   1. /app/data not writable (host bind-mount owned by root)
#   2. /app/config.toml not mounted
#
# Runs as user v4v (UID 1001) per the Dockerfile USER directive.
# Pure POSIX sh so it works on alpine/slim base images alike.

set -eu

DATA_DIR=/app/data
CONFIG_FILE="${V4V_CONFIG:-/app/config.toml}"

fail() {
    # heredoc-style remediation, sent to stderr, then exit 1
    printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2
    shift
    for line in "$@"; do
        printf '  %s\n' "$line" >&2
    done
    printf '\n' >&2
    exit 1
}

# ── data directory must be writable by UID 1001 ─────────────────────────────
if [ ! -d "$DATA_DIR" ] || [ ! -w "$DATA_DIR" ]; then
    fail \
        "$DATA_DIR is not writable by UID 1001 (user 'v4v')." \
        "" \
        "Most likely cause: docker auto-created the bind-mounted host" \
        "directory as root, so the non-root container user cannot write." \
        "" \
        "Fix on the host:" \
        "    mkdir -p ./data" \
        "    sudo chown 1001:1001 ./data" \
        "" \
        "Or use a Docker named volume (no perms dance needed):" \
        "    docker volume create v4v-data" \
        "    docker run ... -v v4v-data:/app/data ..." \
        "" \
        "Or run ./scripts/setup.sh on the host before bringing up compose."
fi

# ── config file must exist + be readable ────────────────────────────────────
if [ ! -r "$CONFIG_FILE" ]; then
    fail \
        "$CONFIG_FILE not found or unreadable." \
        "" \
        "Mount your config into the container:" \
        "    docker run ... -v \$PWD/config.toml:/app/config.toml:ro ..." \
        "" \
        "If you haven't created one yet:" \
        "    cp config.toml.example config.toml" \
        "    \$EDITOR config.toml          # set [lnbits] and [antibot]"
fi

# Hand off to whatever CMD was set (uvicorn, by default).
exec "$@"
