# Quick Start

This file is the shortest reliable path to get `Aptly` running in its current form.

It covers:

- local bot startup
- extension build and loading
- pairing
- remote pairing through a tunnel when the Mac is behind a mobile hotspot

For repository overview, see [`README.md`](./README.md).

## 1. Clone

```bash
git clone <your-remote-url> Aptly
cd Aptly
```

## 2. Prepare Env Files

```bash
cp .env.example .env
cp bot/.env.example bot/.env
cp extension/.env.example extension/.env
```

### Minimum bot settings

Edit [`bot/.env`](./bot/.env) and set:

- `DB_NAME`
- `DB_USER`
- `DB_PASS`
- `DB_PORT`
- `DB_POSTGRES`
- `TELEGRAM_BOT_TOKEN`
- `CHECK_INTERVAL_SECONDS`
- `NOTIFICATION_DELAY`
- `REQUEST_TIMEOUT`
- `REQUEST_DELAY`
- `MAX_RETRIES`

Recommended API settings:

```env
API_HOST=0.0.0.0
API_PORT=8080
```

### Extension settings

`extension/.env` is now only a fallback build-time URL.

Current preferred approach:

- build once
- set the actual backend URL in the popup at runtime

That runtime URL may be:

- `https://your-host`
- `http://your-host:8080`
- `wss://your-host/ws/extension`
- `ws://your-host:8080/ws/extension`

Why:

- you no longer need to rebuild the extension every time the tunnel/domain changes

## 3. Start Bot Dependencies

```bash
cd bot
docker compose up -d --build
```

What this does:

- starts PostgreSQL
- builds and starts the bot container
- exposes bot HTTP API on `localhost:8080`

Important code paths:

- app bootstrap: [`bot/app/main.py`](./bot/app/main.py)
- HTTP + websocket server: [`bot/app/http/server.py`](./bot/app/http/server.py)
- pairing/token storage: [`bot/app/realtime/pairing.py`](./bot/app/realtime/pairing.py)

## 4. Verify Local API

Run:

```bash
curl -X POST http://127.0.0.1:8080/api/pair \
  -H 'Content-Type: application/json' \
  -d '{"pin":"000000"}'
```

Expected result:

- JSON error such as `{"error":"pin is invalid or expired"}`

That is good enough. It proves the API is reachable.

## 5. Start Remote Tunnel When Needed

If the extension runs on another device, especially iPhone/Orion on a different network, direct `localhost` or LAN IP will not work reliably.

Use the tunnel workflow:

```bash
./tools/current-tunnel-url.sh
```

If the helper returns a URL, the tunnel is already running.

If needed, start it manually:

```bash
./tools/cloudflared-quick-tunnel.sh
```

Current design:

- `cloudflared` forwards public HTTPS/WSS traffic to local `127.0.0.1:8080`
- the extension popup stores the backend URL in local storage at runtime

See:

- [`tools/cloudflared-quick-tunnel.sh`](./tools/cloudflared-quick-tunnel.sh)
- [`tools/current-tunnel-url.sh`](./tools/current-tunnel-url.sh)

## 6. Build Extension

```bash
cd extension
bun install
bun run build
```

Optional:

```bash
bunx svelte-check --tsconfig ./tsconfig.json
```

## 7. Load Extension

Load unpacked:

1. Open `chrome://extensions/`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select [`extension/dist`](./extension/dist)

For Orion on iPhone, load the same built extension package using your Orion-compatible flow.

## 8. Pair Extension

### Local same-machine scenario

Use:

```text
http://127.0.0.1:8080
```

or leave the runtime field empty if your build-time fallback is already correct.

### Remote / iPhone / different-network scenario

Use:

```text
https://<current-trycloudflare-url>
```

Get the current URL:

```bash
./tools/current-tunnel-url.sh
```

Then:

1. Open the extension popup.
2. Paste the URL into `Backend URL`.
3. In Telegram request a fresh pairing PIN.
4. Enter the PIN.
5. Click `Connect`.

Why this works:

- popup sends `POST /api/pair`
- background derives `/ws/extension` automatically from the runtime URL
- no rebuild is required for endpoint changes

Relevant code:

- popup UI: [`extension/src/App.svelte`](./extension/src/App.svelte)
- URL normalization and pairing: [`extension/src/background.ts`](./extension/src/background.ts)

## 9. Minimal Functional Check

After pairing:

1. Open the popup.
2. Confirm it shows connected `chat_id`.
3. Open a supported provider page.
4. Click `⚡ Execute Fill`.

You can also enable auto-fill in the popup.

Relevant execution path:

- popup/background vault state: [`extension/src/background.ts`](./extension/src/background.ts)
- tab-side fill: [`extension/src/content.ts`](./extension/src/content.ts)
- rule hydration and domain-specific logic: [`extension/src/injector.ts`](./extension/src/injector.ts)

## 10. Verification Commands

### Bot

```bash
cd bot
python3 -m compileall -q app
```

### Extension

```bash
cd extension
bun run build
```
