# Aptly

`Aptly` is a two-service monorepo for Telegram-driven apartment discovery and browser-side application automation.

It combines:

- a Python bot that scrapes listings, stores state, talks to Telegram, and exposes pairing + websocket endpoints
- a Chrome/Orion-compatible MV3 extension that stores a normalized applicant profile and applies domain-specific autofill rules inside real provider forms

This repository is optimized for a practical workflow:

1. Telegram is the control plane.
2. The browser extension is the execution plane.
3. Pairing is explicit and token-based.
4. Form schemas stay in JSON, not hardcoded in TS.
5. Remote pairing is possible even when the Mac is behind a mobile hotspot, using a public tunnel.

## Repository Map

- [`bot/`](./bot): Telegram bot, scraper engine, API, websocket gateway, DB
- [`extension/`](./extension): Manifest V3 extension, popup UI, background worker, injector
- [`docs/`](./docs): project documentation and operational runbooks
- [`tools/`](./tools): helper scripts for tunnel/autostart workflow
- [`QUICK_START.md`](./QUICK_START.md): shortest path to a working local or remote setup

## What The Project Does

### 1. Scrapes apartment listings

The active scraping loop is started in [`bot/app/main.py`](./bot/app/main.py) and implemented in [`bot/app/scrape_engine.py`](./bot/app/scrape_engine.py).

Current design:

- scraper execution is asynchronous
- only new listings are notified
- user filter matching happens before Telegram delivery
- listing history is persisted, so users are not spammed with duplicates

Why this approach:

- it keeps runtime simple: one Python process owns Telegram polling, API, websocket, and scraping
- it avoids a separate queueing system
- it is sufficient for the current single-source, Telegram-first workflow

### 2. Collects and stores user profile data

The bot drives a sequential FSM profile flow in [`bot/app/telegram/handlers/commands_handler.py`](./bot/app/telegram/handlers/commands_handler.py).

The profile is normalized into stable keys such as:

- `salutation`
- `first_name`
- `last_name`
- `email`
- `phone`
- `street`
- `house_number`
- `zip_code`
- `city`
- `persons_total`
- `wbs_available`
- `wbs_date`
- `wbs_rooms`
- `wbs_income`

Persistence and serialization are implemented in:

- [`bot/app/db/models/models.py`](./bot/app/db/models/models.py)
- [`bot/app/db/services/user_svc.py`](./bot/app/db/services/user_svc.py)

Important current rule:

- `wbs_date` is stored as raw `DD.MM.YYYY`, not ISO date

Why this approach:

- websites accept different UI layouts, but the user profile should stay consistent
- the extension can bind rules to normalized keys without caring where the values came from

### 3. Pairs the browser extension with Telegram

Pairing is implemented by:

- PIN generation and token issuance in [`bot/app/realtime/pairing.py`](./bot/app/realtime/pairing.py)
- HTTP endpoint `POST /api/pair` in [`bot/app/http/server.py`](./bot/app/http/server.py)
- websocket auth in [`bot/app/realtime/gateway.py`](./bot/app/realtime/gateway.py)

Flow:

```text
Telegram user -> requests PIN
Bot -> creates 6-digit PIN with TTL
Extension -> POST /api/pair with PIN
Bot -> returns token + normalized profile
Extension -> opens websocket and authenticates with token
Bot -> can push profile updates and execute_fill events
```

Why this approach:

- no Telegram credentials are ever entered in the extension
- pairing is explicit and revocable
- websocket auth stays short and isolated to a token

### 4. Autofills real provider forms

The extension keeps provider-specific rules in JSON:

- [`extension/autofilled-rules.json`](./extension/autofilled-rules.json)

Runtime execution is split into these modules:

- popup UI and rule editing: [`extension/src/App.svelte`](./extension/src/App.svelte)
- background pairing, vault hydration, websocket, fill orchestration: [`extension/src/background.ts`](./extension/src/background.ts)
- normalized mapping + provider-specific transforms: [`extension/src/injector.ts`](./extension/src/injector.ts)
- page-side application of rules in the tab: [`extension/src/content.ts`](./extension/src/content.ts)
- selector picker: [`extension/src/picker.ts`](./extension/src/picker.ts)

Why JSON rules are used instead of hardcoded selectors in TypeScript:

- form selectors change more often than logic
- non-code updates to selectors are easier to reason about
- `valueKey` lets one profile feed many providers

## Architecture

### Runtime layout

```text
                  +--------------------+
                  | Telegram user       |
                  +----------+---------+
                             |
                             v
                  +--------------------+
                  | bot/app/main.py     |
                  | aiogram + aiohttp   |
                  +----------+---------+
                             |
         +-------------------+-------------------+
         |                                       |
         v                                       v
+---------------------+                 +----------------------+
| ScraperEngine        |                 | API + WebSocket      |
| scrape_engine.py     |                 | server.py/gateway.py |
+----------+----------+                 +----------+-----------+
           |                                        |
           v                                        v
+---------------------+                 +----------------------+
| PostgreSQL          |                 | Browser Extension    |
| users/listings/etc. |                 | MV3 background/popup |
+---------------------+                 +----------------------+
                                                     |
                                                     v
                                           +-------------------+
                                           | Content / Injector|
                                           | real website DOM  |
                                           +-------------------+
```

### Remote pairing over tunnel

This repository now supports a practical mobile workflow:

- the bot can run locally in Docker on the Mac
- `cloudflared` can expose it through a public HTTPS/WSS endpoint
- the extension popup can store a runtime backend URL, so changing the endpoint no longer requires rebuild

Relevant files:

- [`tools/cloudflared-quick-tunnel.sh`](./tools/cloudflared-quick-tunnel.sh)
- [`tools/current-tunnel-url.sh`](./tools/current-tunnel-url.sh)
- [`tools/com.aptly.cloudflared.quick-tunnel.plist`](./tools/com.aptly.cloudflared.quick-tunnel.plist)

Why this was added:

- mobile hotspot setups usually have no router UI
- direct inbound access via public IP often fails because of carrier NAT
- quick tunnels are a pragmatic way to make `/api/pair` and `/ws/extension` reachable from iPhone/Orion

## Why These Technologies Are Used

### Python + aiogram + aiohttp

Used in `bot/` because the project needs:

- Telegram bot interaction
- async scraping
- async DB access
- a lightweight HTTP + websocket server in the same process

This keeps the service small and operationally simple.

### SQLAlchemy + Alembic + PostgreSQL

Used because the project needs durable state for:

- users
- filters
- listing history
- pairing PIN/token lifecycle

Alembic is used because profile fields and pairing schema evolved during development and needed tracked migrations.

### Playwright

Used because listing pages are dynamic and require browser-level DOM/state access.

The active scraper is wired through:

- [`bot/app/parsers/site/inberlinwohnen.py`](./bot/app/parsers/site/inberlinwohnen.py)

### Svelte + Vite + Bun

Used in `extension/` because:

- popup UI is small but stateful
- MV3 build output needs to stay lean
- Vite gives fast iteration and CRX-friendly bundling
- Bun is used as the JS package/runtime tool for the extension project

### Manifest V3

Used because the extension is built around:

- a service worker background script
- content-script based DOM execution
- storage-backed state
- tab-level scripting APIs

See:

- [`extension/manifest.json`](./extension/manifest.json)

## Development Approaches Used In This Repository

### 1. Normalize early, specialize late

Profile fields are normalized in backend storage first, then specialized only when needed in injector logic.

Examples:

- raw profile serialization: [`bot/app/db/services/user_svc.py`](./bot/app/db/services/user_svc.py)
- domain-specific `wbs_income`, `wbs_rooms`, `self_usage`, `always_true`: [`extension/src/injector.ts`](./extension/src/injector.ts)

Why:

- it prevents provider-specific assumptions from leaking into storage and Telegram UX

### 2. Pairing is transport-level, not UI-level

The extension does not contain Telegram-specific logic beyond PIN entry.

Why:

- backend owns trust and token issuance
- extension stays a consumer of profile + fill commands

### 3. Rules are data, not code

`autofilled-rules.json` is loaded at runtime by the background worker and hydrated against profile data.

Why:

- selectors change more often than extension logic
- it is easier to diff and audit

### 4. Failure diagnostics were made explicit

Recent work added clearer pairing diagnostics in the extension:

- missing URL
- invalid URL
- localhost misuse on iPhone
- network request failure
- backend JSON error
- unexpected response format

Code:

- [`extension/src/background.ts`](./extension/src/background.ts)

### 5. Telegram flood control is now respected

Notifier delivery now serializes sends per chat and backs off on `retry_after`.

Code:

- [`bot/app/telegram/notifier/notifier.py`](./bot/app/telegram/notifier/notifier.py)

Why:

- Telegram limits are per chat / per method sensitive
- retry storms are worse than delayed delivery

## Current User Flows

### Listing notifications

```text
Scraper -> apartment entity -> filter match -> notifier -> Telegram chat
```

Relevant code:

- [`bot/app/scrape_engine.py`](./bot/app/scrape_engine.py)
- [`bot/app/db/services/listing_svc.py`](./bot/app/db/services/listing_svc.py)
- [`bot/app/telegram/notifier/notifier.py`](./bot/app/telegram/notifier/notifier.py)

### Profile sync to extension

```text
Telegram FSM -> save profile -> serialize profile -> websocket profile_updated -> extension vault
```

Relevant code:

- [`bot/app/telegram/handlers/commands_handler.py`](./bot/app/telegram/handlers/commands_handler.py)
- [`bot/app/realtime/gateway.py`](./bot/app/realtime/gateway.py)
- [`extension/src/background.ts`](./extension/src/background.ts)

### Manual or automatic fill

```text
popup/config -> hydrated vault -> content/background execution -> DOM actions on provider page
```

Relevant code:

- [`extension/src/App.svelte`](./extension/src/App.svelte)
- [`extension/src/content.ts`](./extension/src/content.ts)
- [`extension/src/injector.ts`](./extension/src/injector.ts)

## Documentation

- [`QUICK_START.md`](./QUICK_START.md) is the main public setup guide.
- Additional maintenance notes live under [`docs/`](./docs).

## Verification

### Bot

```bash
cd bot
python3 -m compileall -q app
```

Full test run depends on a correctly configured bot env and DB.

### Extension

```bash
cd extension
bun run build
```
