# Setup And Full Verification

## Scope

This checklist verifies the repository exactly as it is now.

- Bot parses only `inberlinwohnen.de` via Playwright.
- Telegram sends listing cards with URL `Link` button.
- Bot hosts pairing and persistent websocket connections.
- Extension pairs via PIN and runtime `Backend URL` with `.env` fallback.

## 1. Prerequisites

- Docker + Docker Compose
- Python 3.14+
- Bun
- Chrome/Chromium
- Telegram bot token

## 2. Bot Setup

```bash
cd bot
cp .env.example .env
alembic upgrade head
python3 -m playwright install chromium
```

Start with Docker:

```bash
docker compose up --build -d
docker compose logs -f
```

Or run locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m app.main
```

## 3. Bot Verification

Static checks:

```bash
cd bot
python3 -m compileall -q app
pytest -q
```

Runtime checks:

1. Send `/start`.
2. Configure filter values.
3. Wait for listing notification.
4. Validate message format:
- first line starts with `🏠 <b>Source</b> |`
- empty line before address
- address line has Google Maps link
- fields include district/rent metrics when available
- no inline raw URL line in text
- inline button text is `Link` and opens provider URL.

## 4. Parser Checks

Confirm from code and logs:

- `ALL_SCRAPERS` contains only `InBerlinWohnenScraper`.
- parser file: `bot/app/parsers/site/inberlinwohnen.py`.
- pagination is Playwright-driven.
- parsed listing contains `price`, `cold_rent`, `extra_costs`, `floor`, `district`, `image_url`, `published_at`.

## 5. Extension Setup

```bash
cd extension
bun install
bun run build
```

Optional fallback `.env`:

```bash
cd extension
cat > .env <<'EOF'
VITE_WS_URL=ws://127.0.0.1:8080/ws/extension
EOF
```

Runtime URL rules:

- `127.0.0.1` / `localhost` only work when backend and browser are on the same device
- a Mac LAN IP only works when the iPhone and Mac are on the same network
- if iPhone and Mac are in different networks, use a public domain/IP, VPN, or tunnel
- after editing fallback `.env`, rebuild `extension/dist` before reloading the unpacked extension
- changing popup `Backend URL` does not require rebuild

Optional:

```bash
bunx svelte-check --tsconfig ./tsconfig.json
```

Load unpacked extension from `extension/dist`.

## 6. Extension Verification

Popup checks:

1. `Auto-Fill` toggle works.
2. `Auto-Submit` toggle works.
3. Popup accepts runtime `Backend URL` and persists it.
4. Pairing PIN can be entered and pairing succeeds with valid bot-generated PIN.
4. After pairing, popup shows connected `chat_id` and `Create New Pair` action.
5. Clicking a domain toggles accordion expand/collapse of its rules.
6. Domain tab can be added from active site.
7. Rule rows can be added/removed.
8. Selector picker writes selected selector back into rule.
9. `Execute Fill` triggers content script fill.
10. Export and import of rules work.
11. Base rules are loaded from built `autofilled-rules.json`.

Pairing diagnostics to verify:

1. Empty or invalid backend URL reports a configuration error.
2. `localhost` / `127.0.0.1` reports that external devices must use a reachable host.
3. Unreachable backend reports a network error instead of a generic failure.
4. Invalid or expired PIN still reports backend JSON error.
5. Broken success payload reports unexpected response format.

## 7. iPhone / Orion Notes

When the extension runs inside Orion on iPhone:

- `127.0.0.1` and `localhost` refer to the iPhone itself
- `ws://192.168.x.x:8080/...` works only if the iPhone can reach that private address directly
- if the backend runs on a Mac in another network, private LAN IPs will not work
- for cross-network pairing use a public domain/IP, secure reverse proxy, VPN, or tunnel

Typical working examples for popup `Backend URL`:

```env
http://192.168.1.50:8080
```

Only for same-network iPhone + Mac.

```env
https://bot.example.com
```

For internet-reachable backend.

## 8. Integration Notes to Validate

Current implementation details:

- Bot ws endpoint expects first message `{"type":"authenticate","token":"..."}`.
- Extension background sends `{"type":"authenticate","token":"..."}`.
- Bot listing notifier sends URL button and does not rely on ws fill actions.

This means listing delivery and authenticated extension channel are aligned.

## 9. Current Migration Set

Relevant migration files present:

- `20260320_2041_52ad749421f4_initial.py`
- `20260401_1200_add_user_profile_fields.py`
- `20260401_1900_profile_pairing_fields.py`
- `20260401_2300_persist_extension_pairing.py`
- `20260402_0900_add_special_listing_preference.py`
- `20260402_1015_add_listing_rent_fields.py`
