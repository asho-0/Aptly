# Aptly

## Overview

`Aptly` is a two-service monorepo for Telegram-driven apartment discovery and browser-side form automation.

- `bot/` runs the Telegram bot, PostgreSQL persistence layer, scraping loop, `POST /api/pair`, and the persistent websocket server on the same event loop.
- `extension/` is a Chrome Manifest V3 extension built with Svelte, Vite, and Bun for pairing, receiving profile updates, and executing autofill flows in the browser.

## Architecture

### 1. Bot service

- `aiogram` Telegram worker
- `aiohttp` HTTP + websocket server
- SQLAlchemy + Alembic + PostgreSQL
- pairing PIN generation and token issuance
- FSM-based profile collection and profile synchronization

### 2. Extension service

- Manifest V3 background worker
- popup UI in Svelte
- dynamic schema loading from `autofilled-rules.json`
- websocket authentication using the pairing token
- in-memory hydration of rule values from Telegram profile data

## Core Features

- Telegram filter configuration for apartment search
- Telegram profile collection for autofill data
- 6-digit pairing PIN generation
- `POST /api/pair` token exchange
- websocket `profile_updated` push to a paired extension
- runtime rule hydration without hardcoding form schema in TypeScript
- popup controls for `Auto-Fill`, `Auto-Submit`, `Execute Fill`, selector picking, import, and export

## Tech Stack

### Backend

- Python 3.14+
- aiogram
- aiohttp
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Playwright
- pytest + pytest-asyncio + pytest-mock

### Extension

- Bun
- TypeScript
- Svelte
- Vite
- Vitest
- Testing Library

## Repository Layout

- [`bot`](./bot)
- [`extension`](./extension)
- [`QUICK_START.md`](./QUICK_START.md)
- [`start.sh`](./start.sh)

## Local Development

### Bot

```bash
cd bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.main
```

### Extension

```bash
cd extension
bun install
bun run dev
```

## Test Entry Points

### Bot

```bash
cd bot
.venv/bin/pytest -v
```

### Extension

```bash
cd extension
bun test
```
