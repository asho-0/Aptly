# Testing Architecture

## Scope

The repository test strategy is split by service boundary:

- `bot/tests/` validates persistence, pairing APIs, and Telegram handler logic.
- `extension/tests/` validates popup behavior and browser-side injection behavior.

## Bot Test Layout

### `bot/tests/conftest.py`

The bot fixture layer is PostgreSQL-only and uses the project database helpers:

- loads `bot/.env.test`
- creates a temporary PostgreSQL database with `create_database`
- applies Alembic migrations with `run_migrations`
- disposes the async engine after the session
- drops the temporary database with `drop_database`

### Database lifecycle

The session-scoped database lifecycle is:

1. read `.env.test`
2. derive a unique test database name
3. create the database
4. migrate to `head`
5. open a shared async engine for test execution
6. drop the database after the pytest session

### Per-test transaction isolation

Each test receives:

- a dedicated async SQLAlchemy connection
- one outer transaction
- one async session bound to that connection
- a patched `db.session_context()` and `db.nested_transaction()` layer

At the end of the test:

- the session closes
- the outer transaction rolls back
- the original database manager state is restored

This keeps the migrated schema real while guaranteeing clean data between tests.

## Bot Test Suites

### `bot/tests/test_db.py`

Focus:

- model persistence
- unique constraints
- pairing pin persistence

Covered paths:

- `User`
- `ExtensionPairing`
- `PairingStore.create_pin`

### `bot/tests/test_api.py`

Focus:

- `POST /api/pair`
- valid pairing exchange
- invalid PIN handling
- required payload validation

Covered behavior:

- user profile serialization
- token issuance
- consumed pairing invalidation
- response contract

### `bot/tests/test_handlers.py`

Focus:

- `[🔗 Link Extension]` callback
- FSM field progression
- profile persistence through handler flow
- websocket profile broadcast trigger

Covered behavior:

- pairing PIN delivery to Telegram chat
- FSM state transitions
- final profile save
- `profile_updated` push invocation

## Mocking Strategy

### Bot

The bot suite uses real PostgreSQL persistence and selective mocks for transport boundaries:

- mocked `aiogram.Bot`
- mocked `TelegramNotifier`
- mocked realtime gateway for websocket push assertions
- mocked callback/message objects for handler entry points

Database repositories and services remain real.

## Extension Test Layout

### `extension/tests/App.test.ts`

Focus:

- popup pairing states
- connect / reset-pair UI flow
- domain accordion toggle behavior

Mocked boundaries:

- `chrome.runtime`
- `chrome.storage.local`
- `chrome.storage.session`
- `chrome.tabs`
- `chrome.scripting`

### `extension/tests/injector.test.ts`

Focus:

- runtime fill execution
- event dispatching
- hidden input handling
- click-based rule execution
- auto-submit path

Execution environment:

- `jsdom`
- mocked Chrome messaging contract

## Commands

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
