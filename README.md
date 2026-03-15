# 🏠 Apartment Notifier Bot

An asynchronous Python bot for real estate monitoring. It scrapes **3 websites** every minute, filters listings based on your specific criteria, and instantly sends new matches to Telegram.

---

## 🚀 Key Features

* **Multi-site Scraping:** Parallel data collection from multiple real estate platforms.
* **Flexible Filters:** Configure price, rooms, area, and social status (WBS) directly via chat commands.
* **Smart Notifications:** Prevents duplicates and "warms up" the seen-listings cache on startup.
* **Preview Mode:** Automatically searches for matching listings immediately after filter updates.
* **Full Containerization:** Ready-to-use Docker image with an optimized multi-stage build.

---

## ⚙️ Quick Start

### 1. Environment Setup
Create a `.env` file from the example and fill in your details (Bot Token, Chat ID, DB credentials):
```bash
cp .env.example .env

```

### 2. Launch the Project

Management is handled via the `Makefile`. To build and run the project, execute:

```bash
make build
make up
make logs

```

### 3. Database Initialization

After the first launch, you need to initialize the table structure:

```bash
make db-create
make db-migrate
```

---

## ⌨️ Makefile Commands

Convenient shortcuts for container and database management:

| Command | Description |
| --- | --- |
| `make up` | Start the project in the background (detached) |
| `make down` | Stop and remove containers along with volumes |
| `make build` | Build Docker images |
| `make logs` | View real-time bot logs |
| `make restart` | Restart the bot container |
| `make db-create` | Initialize tables in the database |
| `make db-migrate` | Apply existing Alembic migrations |
| `make make-migration m="text"` | Create a new migration (autogenerate) |
---

## 🤖 Telegram Bot Commands

| Command | Description |
| --- | --- |
| `/start` | Register and view help information |
| `/filter` | Show current search settings |
| `/price 600-1500` | Set price range |
| `/rooms 2-3` | Set number of rooms |
| `/area 50-100` | Set area range in **m²** |
| `/status any` | Set social status (wbs / no_wbs / any) |
| `/pause` / `/resume` | Enable or disable notifications |
| `/reset` | Reset filters to default values |
| `/lang en` | Switch interface language (en/ru) |

---

## 🛠 Tech Stack

* **Language:** Python 3.12+ (Asyncio)
* **Bot Framework:** aiogram 3.x
* **Database:** PostgreSQL
* **Migrations:** Alembic
* **Linting/Formatting:** Ruff & Mypy
* **Orchestration:** Docker & Compose
---
