# ============================================================
# bot_commands.py — Telegram command handler
#
# Dependency flow:
#   CommandHandler → FilterService  (filter read/write)
#                 → StatsService    (/stats command)
#
# Never imports from repositories/ or schemas/ directly.
# ============================================================

import asyncio
import logging
from typing import Optional

import aiohttp

from app_models import ApartmentFilter
from config import settings
from db.services import FilterService, FullStatsResponse, StatsService
from db.schemas.filter import UpdateKeywordsRequest

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

# ── User-facing strings (EN / RU) ─────────────────────────────
T: dict[str, dict[str, str]] = {
    "en": {
        "filter_updated":  "✅ Filter updated!",
        "paused":          "⏸ Notifications paused. Send /resume to continue.",
        "resumed":         "▶️ Notifications resumed!",
        "reset_done":      "🔄 Filters reset to defaults.",
        "unknown_cmd":     "❓ Unknown command. Send /help for the list.",
        "invalid_value":   "⚠️ Invalid value — please enter a number.",
        "status_options":  (
            "Valid options: <code>any</code> | <code>market</code> | "
            "<code>wbs</code> | <code>sozialwohnung</code> | <code>staffelmiete</code>"
        ),
        "no_stats":        "📊 Statistics are not available right now.",
        "lang_changed":    "🌐 Language set to English.",
        "lang_invalid":    "⚠️ Supported languages: <code>en</code>, <code>ru</code>",
        "help": (
            "🤖 <b>Available commands:</b>\n\n"
            "/filter              – show active filters\n"
            "/rooms  1 3          – set room range (min max)\n"
            "/price  500 1500     – set rent range in € (min max)\n"
            "/area   40 100       – set area range in m² (min max)\n"
            "/status wbs          – set social status filter\n"
            "   <i>any | market | wbs | sozialwohnung | staffelmiete</i>\n"
            "/keywords +balcony -garage  – add/remove keywords\n"
            "/pause               – pause notifications\n"
            "/resume              – resume notifications\n"
            "/stats               – DB + Redis statistics\n"
            "/lang en             – switch language (en / ru)\n"
            "/reset               – reset all filters to defaults\n"
            "/help                – this message"
        ),
        "startup": (
            "🤖 <b>Apartment Notifier started!</b>\n\n"
            "Monitoring <b>{count}</b> German real-estate sources.\n"
            "Send /help to see available commands."
        ),
    },
    "ru": {
        "filter_updated":  "✅ Фильтр обновлён!",
        "paused":          "⏸ Уведомления приостановлены. Отправьте /resume для продолжения.",
        "resumed":         "▶️ Уведомления возобновлены!",
        "reset_done":      "🔄 Фильтры сброшены до стандартных значений.",
        "unknown_cmd":     "❓ Неизвестная команда. Отправьте /help для списка.",
        "invalid_value":   "⚠️ Неверное значение — введите число.",
        "status_options":  (
            "Допустимые значения: <code>any</code> | <code>market</code> | "
            "<code>wbs</code> | <code>sozialwohnung</code> | <code>staffelmiete</code>"
        ),
        "no_stats":        "📊 Статистика временно недоступна.",
        "lang_changed":    "🌐 Язык установлен: Русский.",
        "lang_invalid":    "⚠️ Поддерживаемые языки: <code>en</code>, <code>ru</code>",
        "help": (
            "🤖 <b>Доступные команды:</b>\n\n"
            "/filter              – показать активные фильтры\n"
            "/rooms  1 3          – количество комнат\n"
            "/price  500 1500     – аренда в €/мес\n"
            "/area   40 100       – площадь м²\n"
            "/status wbs          – фильтр по типу жилья\n"
            "   <i>any | market | wbs | sozialwohnung | staffelmiete</i>\n"
            "/keywords +балкон -гараж  – ключевые слова\n"
            "/pause               – приостановить уведомления\n"
            "/resume              – возобновить уведомления\n"
            "/stats               – статистика БД и Redis\n"
            "/lang ru             – сменить язык\n"
            "/reset               – сбросить фильтры\n"
            "/help                – эта справка"
        ),
        "startup": (
            "🤖 <b>Бот по поиску квартир запущен!</b>\n\n"
            "Отслеживаю <b>{count}</b> немецких сайтов недвижимости.\n"
            "Отправьте /help для списка команд."
        ),
    },
}


def t(key: str, lang: str | None = None, **kwargs) -> str:
    lang   = lang or settings.BOT_LANGUAGE
    result = T.get(lang, T["en"]).get(key) or T["en"].get(key, key)
    return result.format(**kwargs) if kwargs else result


# ─────────────────────────────────────────────────────────────
class FilterStore:
    """
    In-memory filter state. Persistence delegated to FilterService.
    Passed by reference into CommandHandler and main.run_check().
    """

    def __init__(
        self,
        initial_filter: Optional[ApartmentFilter] = None,
        initial_paused: bool = False,
    ) -> None:
        self._svc    = FilterService()
        self._filter = initial_filter or self._svc.build_default()
        self._paused = initial_paused

    @property
    def filter(self) -> ApartmentFilter:
        return self._filter

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, value: bool) -> None:
        self._paused = value
        asyncio.ensure_future(
            self._svc.set_paused(self._filter, settings.TELEGRAM_CHAT_ID, value)
        )

    def reset(self) -> None:
        self._filter = self._svc.build_default()
        self._paused = False
        asyncio.ensure_future(
            self._svc.save(settings.TELEGRAM_CHAT_ID, self._filter, self._paused)
        )

    def save(self) -> None:
        asyncio.ensure_future(
            self._svc.save(settings.TELEGRAM_CHAT_ID, self._filter, self._paused)
        )

    @property
    def service(self) -> FilterService:
        return self._svc


# ─────────────────────────────────────────────────────────────
class CommandHandler:

    def __init__(self, session: aiohttp.ClientSession, store: FilterStore) -> None:
        self.session    = session
        self.store      = store
        self._stats_svc = StatsService()
        self._offset    = 0

    async def poll_loop(self) -> None:
        logger.info("Telegram command polling started")
        while True:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.warning("Command poll error: %s", exc)
            await asyncio.sleep(2)

    async def _poll_once(self) -> None:
        params = {"timeout": 10, "offset": self._offset, "allowed_updates": ["message"]}
        async with self.session.get(
            f"{TELEGRAM_API}/getUpdates",
            params  = params,
            timeout = aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
        if not data.get("ok"):
            return
        for update in data.get("result", []):
            self._offset = update["update_id"] + 1
            msg = update.get("message", {})
            if str(msg.get("chat", {}).get("id")) != str(settings.TELEGRAM_CHAT_ID):
                continue
            text = msg.get("text", "").strip()
            if text.startswith("/"):
                await self._dispatch(text)

    async def _dispatch(self, text: str) -> None:
        parts = text.split()
        cmd   = parts[0].lower().split("@")[0]
        args  = parts[1:]
        lang  = settings.BOT_LANGUAGE

        logger.debug("Received command: %s args=%s", cmd, args)

        if cmd in ("/help", "/start"):
            await self._reply(t("help"))

        elif cmd == "/filter":
            await self._reply(self.store.filter.summary(lang))

        elif cmd == "/rooms":
            ok = await self.store.service.apply_range_update(
                self.store.filter, settings.TELEGRAM_CHAT_ID, "rooms", args, int
            )
            await self._reply(
                t("filter_updated") + "\n\n" + self.store.filter.summary(lang)
                if ok else t("invalid_value")
            )

        elif cmd == "/price":
            ok = await self.store.service.apply_range_update(
                self.store.filter, settings.TELEGRAM_CHAT_ID, "price", args, float
            )
            await self._reply(
                t("filter_updated") + "\n\n" + self.store.filter.summary(lang)
                if ok else t("invalid_value")
            )

        elif cmd == "/area":
            ok = await self.store.service.apply_range_update(
                self.store.filter, settings.TELEGRAM_CHAT_ID, "area", args, float
            )
            await self._reply(
                t("filter_updated") + "\n\n" + self.store.filter.summary(lang)
                if ok else t("invalid_value")
            )

        elif cmd == "/status":
            ok = await self.store.service.apply_status_update(
                self.store.filter, settings.TELEGRAM_CHAT_ID,
                args[0].lower() if args else "",
            )
            await self._reply(
                t("filter_updated") + "\n\n" + self.store.filter.summary(lang)
                if ok else t("status_options")
            )

        elif cmd == "/keywords":
            add    = [a[1:] for a in args if a.startswith("+")]
            remove = [a[1:] for a in args if a.startswith("-")]
            req    = UpdateKeywordsRequest(chat_id=settings.TELEGRAM_CHAT_ID, add=add, remove=remove)
            await self.store.service.apply_keyword_update(
                self.store.filter, settings.TELEGRAM_CHAT_ID, req
            )
            await self._reply(t("filter_updated") + "\n\n" + self.store.filter.summary(lang))

        elif cmd == "/pause":
            self.store.set_paused(True)
            await self._reply(t("paused"))

        elif cmd == "/resume":
            self.store.set_paused(False)
            await self._reply(t("resumed"))

        elif cmd == "/stats":
            await self._send_stats()

        elif cmd == "/lang":
            await self._change_lang(args)

        elif cmd == "/reset":
            self.store.reset()
            await self._reply(t("reset_done") + "\n\n" + self.store.filter.summary(lang))

        else:
            await self._reply(t("unknown_cmd"))

    async def _send_stats(self) -> None:
        try:
            stats: FullStatsResponse = await self._stats_svc.get_full_stats()
        except Exception as exc:
            logger.error("Failed to fetch stats: %s", exc)
            await self._reply(t("no_stats") + f"\n<code>{exc}</code>")
            return

        lang = settings.BOT_LANGUAGE
        if lang == "ru":
            lines = [
                "📈 <b>Статистика:</b>", "",
                "🗄 <b>PostgreSQL:</b>",
                f"  📦 Объявлений всего:  <b>{stats.total_all_time}</b>",
                f"  🆕 Новых сегодня:     <b>{stats.total_today}</b>",
                "",
                "⚡️ <b>Redis-кэш:</b>",
                f"  👁 Просмотренных:     <b>{stats.redis_seen_count}</b>",
                f"  🪞 Локальное зеркало: <b>{stats.redis_local_mirror}</b>",
                f"  💾 Память:            <b>{stats.redis_memory_mb} МБ</b>",
                "",
                "💰 <b>Цены по источнику:</b>",
            ]
            room_label = "комн."
        else:
            lines = [
                "📈 <b>Statistics:</b>", "",
                "🗄 <b>PostgreSQL:</b>",
                f"  📦 Total listings:    <b>{stats.total_all_time}</b>",
                f"  🆕 New today:         <b>{stats.total_today}</b>",
                "",
                "⚡️ <b>Redis cache:</b>",
                f"  👁 Seen UIDs:         <b>{stats.redis_seen_count}</b>",
                f"  🪞 Local mirror:      <b>{stats.redis_local_mirror}</b>",
                f"  💾 Memory:            <b>{stats.redis_memory_mb} MB</b>",
                "",
                "💰 <b>Prices by source:</b>",
            ]
            room_label = "rooms"

        for row in stats.price_rows:
            lines.append(
                f"  {row.source_slug} · {row.rooms or '?'} {room_label} → "
                f"Ø {row.avg_price:.0f} € "
                f"(min {row.min_price:.0f} / max {row.max_price:.0f})"
            )
        await self._reply("\n".join(lines))

    async def _change_lang(self, args: list[str]) -> None:
        if not args or args[0].lower() not in {"en", "ru"}:
            await self._reply(t("lang_invalid"))
            return
        new_lang = args[0].lower()
        settings.__dict__["BOT_LANGUAGE"] = new_lang
        logger.info("UI language changed to: %s", new_lang)
        await self._reply(t("lang_changed", lang=new_lang))

    async def _reply(self, text: str) -> None:
        try:
            async with self.session.post(
                f"{TELEGRAM_API}/sendMessage",
                json    = {
                    "chat_id":    settings.TELEGRAM_CHAT_ID,
                    "text":       text,
                    "parse_mode": "HTML",
                },
                timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
            ) as resp:
                await resp.json()
        except Exception as exc:
            logger.warning("Failed to send Telegram reply: %s", exc)