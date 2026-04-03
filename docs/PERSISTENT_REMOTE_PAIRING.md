# Persistent Remote Pairing

## Goal

Make Aptly pairing work from iPhone/Orion when the Mac runs behind a mobile hotspot, without router access.

## Why this is needed

With a mobile hotspot there is usually:

- no router UI
- no inbound port forwarding
- carrier NAT between the internet and your Mac

That means `ws://<public-ip>:8080/ws/extension` is usually not reachable from iPhone even if Docker exposes port `8080`.

## Chosen approach

We use:

1. local Docker bot on the Mac
2. `cloudflared` quick tunnel from Mac to the public internet
3. runtime-configurable backend URL inside the extension popup

This avoids rebuilds every time the endpoint changes.

## Architecture

```text
iPhone / Orion Extension
        |
        | HTTPS POST /api/pair
        | WSS /ws/extension
        v
Cloudflare Quick Tunnel
        |
        | forwards to local machine
        v
Mac localhost:8080
        |
        v
Docker container: apartment_bot
```

## Why this works better than direct public IP

Direct public IP requires:

- reachable public address
- no carrier NAT
- inbound route to port 8080
- firewall openness

On a mobile hotspot this is commonly unavailable.

A tunnel works differently:

- your Mac initiates the outbound connection
- Cloudflare publishes a temporary public HTTPS/WSS endpoint
- iPhone connects to that endpoint

## Runtime URL strategy

The extension now supports a runtime backend URL in the popup.

Accepted formats:

- `https://host`
- `http://host:8080`
- `wss://host/ws/extension`
- `ws://host:8080/ws/extension`

How normalization works:

```text
https://example.com        -> apiBase=https://example.com
                              wsUrl=wss://example.com/ws/extension

wss://example.com/ws/extension -> apiBase=https://example.com
                                  wsUrl=wss://example.com/ws/extension
```

Relevant code:

- [background.ts](../extension/src/background.ts)
- [App.svelte](../extension/src/App.svelte)

## Permanent vs semi-permanent

What is permanent now:

- extension no longer depends on rebuild for endpoint changes
- Docker bot is configured to listen on `0.0.0.0:8080`
- quick tunnel can be auto-started on the Mac

What is still temporary:

- `trycloudflare.com` quick tunnel URLs are ephemeral

To get a truly stable fixed URL you need:

- a named Cloudflare Tunnel with your account and domain
- or another stable public reverse proxy / VPN ingress

## Startup flow

```text
1. Docker starts bot
2. cloudflared starts outbound tunnel to localhost:8080
3. cloudflared prints current public URL
4. you paste current URL into extension popup once
5. extension stores it in local storage
6. pairing and websocket use this runtime URL
```

## Helper scripts

Start tunnel:

- [cloudflared-quick-tunnel.sh](../tools/cloudflared-quick-tunnel.sh)

Read current URL:

- [current-tunnel-url.sh](../tools/current-tunnel-url.sh)

Examples:

```bash
./tools/cloudflared-quick-tunnel.sh
```

```bash
./tools/current-tunnel-url.sh
```

## Pairing sequence

```text
Telegram bot -> sends fresh PIN
Extension popup -> sends POST /api/pair to tunnel base URL
Bot -> returns token + profile
Extension -> stores token
Extension background -> opens websocket /ws/extension
Bot -> authenticates extension
```

## Failure modes

### 1. `localhost` / `127.0.0.1`

On iPhone this points to the iPhone itself.

### 2. LAN IP

Works only when iPhone and Mac are on the same network.

### 3. Public IP on mobile hotspot

Often blocked by carrier NAT or missing inbound routing.

### 4. Tunnel URL rotated

Quick tunnel URLs change after restart.
The extension no longer needs rebuild, but the popup URL must be updated.

## Recommended way to operate

1. Start Docker bot.
2. Start cloudflared quick tunnel.
3. Run `./tools/current-tunnel-url.sh`.
4. Paste the resulting `https://...trycloudflare.com` into the popup backend URL field.
5. Request a fresh PIN in Telegram.
6. Pair.

## If you want a true fixed domain later

Use a named Cloudflare Tunnel with your own domain and then set:

```text
https://bot.example.com
```

in the popup once.
