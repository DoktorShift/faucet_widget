# Web Faucet

A self-hosted Lightning sats faucet.
Onboard visitors of a website by gifting them Bitcoin (sats) to their own wallet.

Built for [21m.art](https://21m.art) and the 21-bitcoin note project.

## Stack

* **Backend**: FastAPI · LNbits Withdraw extension · SQLite
* **Frontend**: Vite · Vue 3 · Tailwind
* **Embed**: vanilla JS in a Shadow DOM, ~5 kB
* **Deploy**: Docker · Cloudflared

## Features

* Self-hosted anti-bot (HMAC proof-of-work + honeypot + time-gate). No third-party captcha.
* Single-use LNURL withdraw per claim. Amount locked, not tamperable.
* Per-IP cooldown + daily cap. All in SQLite, no Redis.
* Drop-in `<script>` embed for any host page (WordPress, static, anything).
* DE + EN.

## 30-second start

```sh
cp config.toml.example config.toml      # set your LNbits keys + a random HMAC secret
pip install -e .
npm install && npm run build
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-server-header
```

Open `http://localhost:8000`.

Need a random secret (HMAC)? `python3 -c "import secrets; print(secrets.token_hex(32))"`

## Read next

* [DEPLOY.md](DEPLOY.md): how to ship it (Docker, Cloudflared, persistence)
* [WORDPRESS.md](WORDPRESS.md): three copy-paste integrations for WP
* [config.toml.example](config.toml.example): every knob, documented

## License

AGPL-3.0-or-later. See [`LICENSE`](LICENSE).
