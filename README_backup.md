# 🏠 Apartment Notifier Bot

Async Python bot that scrapes **5 real-estate websites** every minute,
filters listings by your criteria, and sends new matches straight to Telegram.

---

## 📁 Project structure

```
apartment_notifier/
├── main.py              ← async scheduler & entry point
├── config.py            ← all settings & filters in one place
├── models.py            ← Apartment dataclass + Telegram formatter
├── notifier.py          ← async Telegram sender (text + photo)
├── state.py             ← JSON-backed "seen IDs" store
├── scrapers/
│   ├── __init__.py      ← exports ALL_SCRAPERS list
│   ├── base.py          ← BaseScraper (fetch + retry + helpers)
│   └── sites.py         ← 5 concrete scrapers
├── requirements.txt
└── README.md
```

---

## ⚙️ Quick start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create a Telegram bot
1. Open [@BotFather](https://t.me/botfather) → `/newbot`
2. Copy the **token**
3. Send any message to your new bot, then visit:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Copy `result[0].message.chat.id` — that's your **chat ID**

### 3. Set environment variables
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-..."
export TELEGRAM_CHAT_ID="987654321"
```
Or edit `config.py` directly.

### 4. Tune your filters (`config.py`)
```python
FILTER = ApartmentFilter(
    min_rooms     = 1,
    max_rooms     = 3,
    min_sqm       = 35.0,
    max_sqm       = 90.0,
    min_price     = 400.0,
    max_price     = 1500.0,
    social_status = "any",         # "any" | "market" | "subsidy" | "social_housing"
    include_keywords = [],         # e.g. ["pet friendly", "parking"]
    exclude_keywords = ["office"], # exclude listings with these words
)
```

### 5. Run
```bash
python main.py
```

---

## 🌐 Scraped sites

| # | Class | Site | Notes |
|---|-------|------|-------|
| 1 | `ZillowScraper` | Zillow Rentals | 3 pages, sq ft → m² |
| 2 | `CraigslistScraper` | Craigslist NYC apts | Section 8 detection |
| 3 | `ApartmentsDotComScraper` | Apartments.com | Affordable badge |
| 4 | `SocialHousingPortalScraper` | NYC Housing Connect | AMI / subsidised |
| 5 | `RealtorScraper` | Realtor.com | 3 pages, floor detection |

> **Adapting to a new site**: create a class that extends `BaseScraper`,
> set `slug`, `name`, `base_url`, implement `parse_listings()`,
> then add it to `ALL_SCRAPERS` in `scrapers/__init__.py`.

---

## 📬 Telegram message format

```
🏠  <Title>
🌐  Zillow Rentals

💰  Price:         $1,200 USD
🚪  Rooms:         2
📐  Area:          79.0 m²
🏢  Floor:         3/9
📍  Location:      Manhattan, 123 Main St
📋  Social status: 🏦 Market price
📅  Published:     2024-05-01

🔗  View announcement
```

---

## 🔧 Adding a new scraper in 3 steps

```python
# scrapers/sites.py
class MySiteScraper(BaseScraper):
    slug     = "mysite"
    name     = "My Site"
    base_url = "https://mysite.com/rentals"

    def parse_listings(self, soup, page_url):
        apartments = []
        for card in soup.select(".listing-card"):
            apartments.append(Apartment(
                id     = self.make_id(card["data-id"]),
                source = self.name,
                url    = card.select_one("a")["href"],
                title  = self.safe_text(card.select_one(".title")),
                price  = self.safe_float(self.safe_text(card.select_one(".price"))),
                rooms  = self.safe_int(self.safe_text(card.select_one(".beds"))),
                sqm    = ...,
                social_status = "market",
            ))
        return apartments

# scrapers/__init__.py  ← add MySiteScraper to ALL_SCRAPERS
```

---

## 📝 Filters reference

| Field | Type | Description |
|-------|------|-------------|
| `min_rooms` / `max_rooms` | int | Number of bedrooms |
| `min_sqm` / `max_sqm` | float | Area in m² |
| `min_price` / `max_price` | float | Monthly rent / asking price |
| `social_status` | str | `"any"` \| `"market"` \| `"subsidy"` \| `"social_housing"` |
| `include_keywords` | list[str] | Title/description must contain at least one |
| `exclude_keywords` | list[str] | Title/description must contain none |