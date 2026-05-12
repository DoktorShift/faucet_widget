# Troubleshooting

Common deploy issues with one-line fixes. Pull-requests welcome to add more.

---

## 1. Container restart loop · `sqlite3.OperationalError: unable to open database file`

**Cause.** Docker auto-created the bind-mounted `./data` directory as root.
The container runs as user `v4v` (UID 1001) and can't write to a root-owned
dir.

**Fix.** Run the host-side setup helper once:

```sh
./scripts/setup.sh
```

Or do it manually:

```sh
mkdir -p ./data
sudo chown 1001:1001 ./data
```

Alternative: switch to a Docker named volume in `docker-compose.yml`
(replace `./data:/app/data` with `v4v-data:/app/data`); Docker manages the
ownership and you skip the issue.

---

## 2. Cloudflared cannot reach the service

**Symptom.** Tunnel logs say `connection refused` or `no route to host`.
The widget container is up, but the tunnel is on a different container/LXC.

**Cause.** `ports: "127.0.0.1:8000:8000"` exposes the service to the widget
container's loopback only. The separate tunnel container can't reach it.

**Fix.** Pick the matching topology from [DEPLOY.md §4](DEPLOY.md#4-deployment-topologies):

* tunnel in a separate LXC → bind to the widget host's LAN-IP (pattern B)
* tunnel in the same compose → use a shared Docker network and `expose:`
  instead of `ports:` (pattern C)

---

## 3. Wallet says "no balance" or "withdraw failed" after a successful claim

**Cause.** The dedicated LNbits faucet wallet is empty.

**Fix.** Top up the wallet on lnbits. Track usage proactively:

```sh
curl https://value4value.eu/api/health
```

`total_minted_count * claim.amount_sats` should stay well below the wallet's
balance. The `low_pot_warning` flag in `/api/health` also tells you when the
day's cap is near.

---

## 4. `/api/health` returns 503 with `lnbits_reachable: false`

**Cause.** Your LNbits server is unreachable, or the admin key in
`config.toml` is wrong.

**Fix.** Test the key directly against your LNbits server:

```sh
curl -H "X-Api-Key: <admin_key>" \
  https://<your-lnbits-host>/withdraw/api/v1/links?limit=1
```

* `401` → key is wrong, regenerate from the LNbits UI
* connection error → LNbits is down, or `lnbits.url` in `config.toml` is
  pointing at the wrong host

---

## 5. The button on my WordPress page does nothing

See the dedicated troubleshooting table in
[WORDPRESS.md](WORDPRESS.md#how-to-verify) which covers CORS, CSP, and
`wp_kses` sanitiser cases.
