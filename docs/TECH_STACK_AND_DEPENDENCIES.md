# Tech Stack And Dependencies

## Overview

Repository has two active components:

- `bot/` - Telegram bot + scraper + DB + API/WebSocket
- `extension/` - Chrome MV3 autofiller (popup + content + background worker)

## Bot Stack (`bot/`)

- Python 3.14
- asyncio
- aiogram 3.26
- aiohttp 3.13
- SQLAlchemy 2.0 + asyncpg + psycopg2
- Alembic
- Playwright 1.55 (Chromium runtime)
- PostgreSQL 16 (via `docker-compose`)
- pydantic + pydantic-settings

Main backend responsibilities:

- Telegram UI and FSM profile flow (`commands_handler.py`)
- Filter persistence and notification history
- Listing upsert/dedup in DB
- Scraping cycle (`scrape_engine.py`)
- PIN generation for pairing (`PairingStore.create_pin`)
- `POST /api/pair` PIN verification and token issuance
- `GET /ws/extension` persistent websocket auth (`authenticate` + token)
- websocket `profile_updated` broadcast on profile save

## Extension Stack (`extension/`)

- TypeScript
- Svelte 4
- Vite 4 + `@crxjs/vite-plugin`
- TailwindCSS + PostCSS
- Chrome Extension Manifest V3

Current extension modules:

- `App.svelte` popup with:
- auto-fill toggle
- auto-submit toggle
- pairing PIN connect state + paired state (`chat_id` + re-pair action)
- runtime `Backend URL` field stored in extension local storage
- domain accordion toggle behavior
- domain rule editor
- export/import
- `background.ts` service worker with:
- runtime backend URL resolution from storage with fallback to `import.meta.env.VITE_WS_URL`
- human-readable backend URL validation and pairing diagnostics
- `/api/pair` PIN exchange
- websocket `authenticate` token flow
- dynamic schema fetch `fetch(chrome.runtime.getURL('autofilled-rules.json'))`
- normalized profile -> rule hydration
- `content.ts` page-side rule executor and auto/manual triggers
- `injector.ts` mapper for domain-specific value formatting and DOM actions
- `picker.ts` selector picker

## Data Model

### Bot DB tables

- `user`
- `filter`
- `listing`
- `notified_listing`
- `extension_pairing`

Important listing fields:

- `price`
- `cold_rent`
- `extra_costs`
- `rooms`
- `sqm`
- `floor`
- `address`
- `district`
- `image_url`
- `published_at`

### Extension local storage

- `vaultData`:
- `autoFillEnabled`
- `autoSubmitEnabled`
- `backendUrl`
- `domainRules`
- `pairPin`
- `extensionToken`
- `pairedChatId`
- `profile`
- temporary selector key `_tempPickedSelector`

Normalized profile fields:

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

`wbs_date` is persisted and sent to the extension as a raw `DD.MM.YYYY` string.

## Parser Architecture (Current)

- Active scraper list: `ALL_SCRAPERS = [InBerlinWohnenScraper]`
- Scraper type: Playwright dynamic parsing
- Source: `inberlinwohnen.de` only
- Extraction strategy:
- read Livewire snapshot payloads in page DOM
- parse rents, rooms, sqm, floor, district, status, image, published_at
- paginate through site controls until exhausted/duplicated fingerprint

## Telegram Delivery Behavior

- Listing text is generated in `Apartment.to_telegram_message`.
- Header format is `🏠 <b>Source</b> | Title`.
- Cards include image when available (`send_photo` fallback to text).
- Reply markup uses URL button `Link` (`listing_link_keyboard`).
- Bot-triggered extension submit buttons are not used in current notifier flow.

## Integration Status: Bot ↔ Extension

Bot realtime contract expects:

- ws message `authenticate` with token issued by `/api/pair`

Current extension sends:

- ws message `authenticate` with token
- handles `profile_updated` and `execute_fill`

## Verification Commands

### Bot

```bash
cd bot
alembic upgrade head
python3 -m playwright install chromium
python3 -m compileall -q app
pytest -q
```

### Extension

```bash
cd extension
bun install
bun run build
bunx svelte-check --tsconfig ./tsconfig.json
```
