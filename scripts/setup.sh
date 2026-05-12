#!/usr/bin/env bash
# value4value first-deploy helper. Idempotent: safe to run multiple times.
#
# 1. Creates ./data with ownership matching the container's UID 1001
# 2. Copies config.toml.example to config.toml if missing
# 3. Generates a random HMAC secret if the placeholder is still present
#
# Run once from the project root before `docker compose up`.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT=$(pwd)

# Container-side UID/GID. Must match the v4v user in the Dockerfile.
V4V_UID=1001
V4V_GID=1001

step() { printf '\n  \033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

# Cross-platform sed -i (BSD/macOS needs an empty string after -i)
sed_inplace() {
    if sed --version >/dev/null 2>&1; then
        sed -i "$@"        # GNU sed
    else
        sed -i '' "$@"     # BSD/macOS sed
    fi
}

random_hex_32() {
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import secrets; print(secrets.token_hex(32))'
    elif command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
    else
        echo "ERROR: neither python3 nor openssl available to generate a secret" >&2
        exit 1
    fi
}

echo
echo "  value4value setup"
echo "  ─────────────────"

# ── 1. data directory ───────────────────────────────────────────────────────
step "1/3  data directory"

if [ ! -d "$ROOT/data" ]; then
    mkdir -p "$ROOT/data"
    ok "created ./data"
else
    ok "./data already exists"
fi

# Touch a marker so chown has something even if the dir was just made
touch "$ROOT/data/.gitkeep"

# Try chown without sudo first (works if we already own the dir or are root)
if chown "$V4V_UID:$V4V_GID" "$ROOT/data" 2>/dev/null; then
    ok "chowned ./data to $V4V_UID:$V4V_GID"
elif command -v sudo >/dev/null 2>&1; then
    if sudo -n true 2>/dev/null; then
        sudo chown -R "$V4V_UID:$V4V_GID" "$ROOT/data"
        ok "chowned ./data to $V4V_UID:$V4V_GID (via sudo)"
    else
        warn "ownership change needs sudo; please run:"
        echo "         sudo chown -R $V4V_UID:$V4V_GID ./data"
    fi
else
    warn "no sudo available; please ensure ./data is writable by UID $V4V_UID"
fi

# ── 2. config file ──────────────────────────────────────────────────────────
step "2/3  config file"

if [ -f "$ROOT/config.toml" ]; then
    ok "config.toml already exists (not overwriting)"
else
    cp "$ROOT/config.toml.example" "$ROOT/config.toml"
    ok "copied config.toml.example → config.toml"
fi

# ── 3. HMAC secret ──────────────────────────────────────────────────────────
step "3/3  HMAC secret"

if grep -q 'hmac_secret = "REPLACE_ME' "$ROOT/config.toml"; then
    SECRET=$(random_hex_32)
    sed_inplace "s|hmac_secret = \"REPLACE_ME[^\"]*\"|hmac_secret = \"$SECRET\"|" \
        "$ROOT/config.toml"
    ok "generated and inserted a 64-char HMAC secret"
else
    ok "HMAC secret already set"
fi

cat <<EOF

  Done. Next steps:

    1. Edit config.toml. Set [lnbits] wallet_id + admin_key
    2. Update [app] base_url + cors_origins to your real domain
    3. Pick a deployment topology in DEPLOY.md, then:
         docker compose up -d

EOF
