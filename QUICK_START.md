# Quick Start

## 1. Clone

```bash
git clone <your-remote-url> Aptly
cd Aptly
```

## 2. Prepare Environment Files

```bash
cp .env.example .env
cp bot/.env.example bot/.env
cp extension/.env.example extension/.env
```

Set at minimum:

- `bot/.env`: PostgreSQL credentials and `TELEGRAM_BOT_TOKEN`
- `extension/.env`: `VITE_WS_URL=ws://127.0.0.1:8080/ws/extension`

## 3. Prepare PostgreSQL

Create a PostgreSQL database that matches the values in `bot/.env`.

## 4. Start Everything

```bash
chmod +x start.sh
./start.sh
```

## 5. Manual Alternative

### Bot

```bash
cd bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m playwright install chromium
python -m app.main
```

### Extension

```bash
cd extension
bun install
bun run dev
```

## 6. Load the Extension

```bash
cd extension
bun run build
```

Load `extension/dist` in `chrome://extensions` with Developer Mode enabled.

## 7. Pair the Extension

1. Open the Telegram bot and send `/start`.
2. Use `🔗 Link Extension` to generate a PIN.
3. Open the extension popup.
4. Enter the PIN and connect.

## 8. Run Tests

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
