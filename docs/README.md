# Docs

This directory documents the **current** repository state for:

- `bot/` (Python Telegram + scraping backend + API/WebSocket)
- `extension/` (MV3 autofill extension)

## Files

- `PERSISTENT_REMOTE_PAIRING.md` - remote pairing architecture, tunnel workflow, and runtime URL strategy
- `TECH_STACK_AND_DEPENDENCIES.md` - stack, architecture, storage, contracts
- `SETUP_AND_FULL_VERIFICATION.md` - full validation checklist

## Current Runtime Snapshot

- Only one active scraper is wired: `InBerlinWohnenScraper`.
- Parser is Playwright-based and paginates through `inberlinwohnen.de`.
- Telegram listing message header format is `🏠 <b>Source</b> | Title` with a blank line before address.
- Telegram listing cards use URL button `Link` (direct provider URL).
- Bot generates 6-digit pairing PINs and stores them in DB.
- Bot exposes `POST /api/pair` and websocket `/ws/extension` on the same event loop.
- Bot profile is normalized to `salutation`, `first_name`, `last_name`, `email`, `phone`, `street`, `house_number`, `zip_code`, `city`, `persons_total`, `wbs_available`, `wbs_date`, `wbs_rooms`, `wbs_income`.
- `wbs_date` is stored and broadcast as raw `DD.MM.YYYY`.
- Extension uses PIN-only pairing UI with unpaired/paired states, authenticates websocket using token, and hydrates `domainRules` from dynamic `autofilled-rules.json` plus normalized user profile data via `valueKey`.

