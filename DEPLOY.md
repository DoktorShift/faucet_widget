# Deployment

This is meant for a single Linux host (Proxmox VM, root server, Raspberry Pi).
Front the service with Cloudflared (recommended, no port forwarding) or a
reverse proxy of your choice. Bind the app itself to localhost.

## What you need

* A Linux host with Docker, or Python 3.11+ and Node 20+
* An LNbits server you control
* A domain pointing at the host (e.g. `YourDomain.de`)

## 1. Backend config

```sh
cp config.toml.example config.toml
```

Edit the file. The non-obvious bits:

```toml
[lnbits]
url        = "https://lnbits.com"          # your LNbits server
wallet_id  = "<wallet id>"                # find under "API info" on the wallet page
admin_key  = "<admin key>"                # required to create withdraw links

[antibot]
hmac_secret = "<64 hex chars>"            # python3 -c "import secrets; print(secrets.token_hex(32))"

[app]
cors_origins = [                          # remove localhost in prod
  "https://value4value.eu",
  "https://21m.art",
]
```

Use a **dedicated** LNbits wallet for the faucet. Fund it with only what you
are happy to give away. The admin key has full rights over the wallet's funds.

## 2. Run as a container (recommended)

```sh
docker build -t value4value .

docker run -d --name value4value --restart unless-stopped \
  -v $PWD/config.toml:/app/config.toml:ro \
  -v $PWD/data:/app/data \
  -p 127.0.0.1:8000:8000 \
  value4value
```

Important: bind to `127.0.0.1`, never `0.0.0.0`. The app trusts the
`CF-Connecting-IP` and `X-Forwarded-For` headers; exposing the port directly
lets attackers spoof IPs and bypass the rate limiter.

## 3. Run without Docker

```sh
pip install -e .
npm install && npm run build

uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 \
  --no-server-header --no-date-header \
  --proxy-headers --forwarded-allow-ips '*'
```

`systemd` unit example: see [`scripts/value4value.service`](scripts/value4value.service).

## 4. Front with Cloudflared

```yaml
# /etc/cloudflared/config.yml
tunnel: <YOUR-TUNNEL-UUID>
credentials-file: /etc/cloudflared/<UUID>.json

ingress:
  - hostname: value4value.eu
    service: http://127.0.0.1:8000
  - service: http_status:404
```

```sh
sudo cloudflared service install
sudo systemctl restart cloudflared
```

DNS for `value4value.eu` should be a CNAME to `<UUID>.cfargotunnel.com`
(Cloudflared sets this up if you use `cloudflared tunnel route dns`).

## 5. Persistence

The only state lives in `./data/claims.sqlite` (rate-limit and nonce tables).
Back it up if claim history matters to you. Otherwise: rebuild wipes nothing,
the volume mount keeps the database between container restarts.

## 6. Resetting state during testing

```sh
./scripts/reset-claims.sh             # wipe everything (claims, nonces, throttle log)
./scripts/reset-claims.sh --soft      # only IP cooldowns and nonces
```

## 7. Monitoring

`/api/health` is the single contract. Two patterns, pick one or both.

### 7a. Pull-based monitoring (recommended baseline)

Point UptimeRobot, Healthchecks.io, k8s readiness probe, or anything else at:

```
GET https://value4value.eu/api/health
```

HTTP semantics:

| Code | Meaning |
| :--- | :--- |
| `200` | Service healthy. `low_pot` and `pot_empty` also return 200 because they are operational signals, not outages. |
| `503` | LNbits unreachable. Page someone. |

Response body (stable contract, fields may be added but not removed):

```json
{
  "status": "healthy",
  "ok": true,
  "lnbits_reachable": true,

  "daily_cap": 50,
  "today_count": 12,
  "today_sats": 252,
  "remaining_today": 38,
  "low_pot_warning": false,

  "total_minted_count": 145,
  "total_redeemed_count": 122,
  "redemption_rate": 0.84,
  "last_redemption_at": 1778460823
}
```

`status` is one of `healthy`, `low_pot`, `pot_empty`, `degraded`.
The container's `HEALTHCHECK` polls this every 30 s already.

### 7b. Push-based alerts (optional)

When you want to get notified the moment things change without setting up a
third-party monitor:

```toml
[alerts]
on_health_change      = ["https://hooks.slack.com/services/T0.../B0.../..."]
poll_interval_seconds = 60
low_pot_threshold_pct = 20
```

A background task snapshots state every `poll_interval_seconds` and POSTs to
each URL **only on transitions** (healthy ↔ degraded ↔ low_pot ↔ pot_empty).
Steady state is silent. Discord webhooks accept the Slack format.

The payload is dual-purpose:

```json
{
  "text": ":warning: faucet low pot: less than 10/50 claims left today",
  "event": "health_change",
  "data": {
    "from": "healthy", "to": "low_pot",
    "lnbits_reachable": true,
    "today_count": 40, "remaining_today": 10, "daily_cap": 50
  }
}
```

### 7c. Redemption-event webhooks (optional)

To get notified when an actual user wallet picks up the sats (not just when
the link is minted), point `webhooks.on_claim_redeemed` at your URL:

```toml
[webhooks]
on_claim_redeemed = ["https://hooks.slack.com/...", "https://hooks.zapier.com/..."]
timeout_seconds   = 10
```

Requires `app.base_url` to be HTTPS so LNbits can reach the receiver
endpoint `POST /api/webhook/lnbits/{token}`. The token is a 128-bit random
secret stored alongside each claim. Callbacks with unknown tokens get a
silent `404`. The same `claim_redeemed` event also feeds the
`total_redeemed_count` field returned by `/api/health` regardless of
forwarding being enabled.

## 8. Updates

```sh
git pull
docker build -t value4value .
docker stop value4value && docker rm value4value
# then re-run the `docker run` from step 2
```

Or without Docker: `git pull && pip install -e . && npm run build && systemctl restart value4value`.

## 9. Done. What's next

* Put the button on your homepage: see [WORDPRESS.md](WORDPRESS.md).
* Monitor `today_sats` against `daily_cap` via `/api/health` and watch your wallet.
* When you change `claim.amount_sats` or `claim.link_title`, restart the service.
