FILTER_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "header": "📊 Active filters:",
        "rooms": "🚪 Rooms",
        "area": "📐 Area",
        "price": "💰 Price",
        "status": "📋 Status",
        "any": "any",
        "sqm_unit": "m²",
        "price_unit": "€/mo",
        "none": "–",
    },
    "ru": {
        "header": "📊 Активные фильтры:",
        "rooms": "🚪 Комнаты",
        "area": "📐 Площадь",
        "price": "💰 Цена",
        "status": "📋 Статус",
        "any": "любой",
        "sqm_unit": "м²",
        "price_unit": "€/мес",
        "none": "–",
    },
}

APARTMENT_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "address": "📍 Address:",
        "rooms": "🚪 Rooms:",
        "area": "📐 Area:",
        "cold_rent": "🧊 Cold rent:",
        "extra_costs": "🔌 Extra costs:",
        "total_rent": "💵 Total rent:",
        "wbs_yes": "✅ required",
        "wbs_no": "❌ not required",
        "wbs_label": "📜 WBS:",
        "floor": "🏢 Floor:",
        "published": "🕒 Published:",
        "area_unit": "m²",
    },
    "ru": {
        "address": "📍 Адрес:",
        "rooms": "🚪 Комнат:",
        "area": "📐 Площадь:",
        "cold_rent": "🧊 Холодная аренда:",
        "extra_costs": "🔌 Доп. расходы:",
        "total_rent": "💵 Общая аренда:",
        "wbs_yes": "✅ требуется",
        "wbs_no": "❌ не требуется",
        "wbs_label": "📜 WBS:",
        "floor": "🏢 Этаж:",
        "published": "🕒 Опубликовано:",
        "area_unit": "м²",
    },
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "filter_updated": "✅ Filter updated!",
        "preview_searching": "🔍 Searching current listings with your new filter…",
        "preview_none": "📭 No matching listings found right now. You'll be notified when new ones appear.",
        "paused": "⏸ Notifications paused. Send /resume to continue.",
        "resumed": "▶️ Notifications resumed!",
        "reset_done": "🔄 Filters reset to defaults.",
        "unknown_cmd": "❓ Unknown command. Send /help for the list.",
        "invalid_value": "⚠️ Invalid value. Use numbers, e.g.:\n/price 500 1500\n/area 30 80\n/rooms 2",
        "status_options": "Valid options: any | market | wbs",
        "lang_changed": "🌐 Language set to English.",
        "lang_invalid": "⚠️ Supported languages: en, ru",
        "reseen_done": "🔄 Cleared {count} seen UIDs. Re-sending preview…",
        "help": (
            "🤖 Available commands:\n\n"
            "/filter – show active filters\n"
            "/rooms 1 3 – set room range (min max)\n"
            "/price 500 1500 – set rent range in € (min max)\n"
            "/area 40 100 – set area range in m²\n"
            "/status wbs – set social status filter (any | wbs | market)\n"
            "/pause – pause notifications\n"
            "/resume – resume notifications\n"
            "/reseen – clear seen cache and re-send preview\n"
            "/lang en – switch language (en / ru)\n"
            "/reset – reset all filters to defaults\n"
            "/help – this message"
        ),
        "startup": (
            "🤖 Apartment Notifier started!\n\n"
            "Monitoring {count} German real-estate sources.\n"
            "Send /help to see available commands."
        ),
    },
    "ru": {
        "filter_updated": "✅ Фильтр обновлён!",
        "preview_searching": "🔍 Ищу текущие объявления с новым фильтром…",
        "preview_none": "📭 Подходящих объявлений пока нет. Вы получите уведомление, когда появятся новые.",
        "paused": "⏸ Уведомления приостановлены. Отправьте /resume для продолжения.",
        "resumed": "▶️ Уведомления возобновлены!",
        "reset_done": "🔄 Фильтры сброшены до стандартных значений.",
        "unknown_cmd": "❓ Неизвестная команда. Отправьте /help для списка.",
        "invalid_value": "⚠️ Неверное значение. Используйте числа, например:\n/price 500 1500\n/area 30 80\n/rooms 2",
        "status_options": "Допустимые значения: any | market | wbs",
        "lang_changed": "🌐 Язык установлен: Русский.",
        "lang_invalid": "⚠️ Поддерживаемые языки: en, ru",
        "reseen_done": "🔄 Очищено {count} просмотренных UID. Отправляю превью…",
        "help": (
            "🤖 Доступные команды:\n\n"
            "/filter – показать активные фильтры\n"
            "/rooms 1 3 – количество комнат\n"
            "/price 500 1500 – аренда в €/мес\n"
            "/area 40 100 – площадь в м²\n"
            "/status wbs – фильтр по типу жилья (any | wbs | market)\n"
            "/pause – приостановить уведомления\n"
            "/resume – возобновить уведомления\n"
            "/reseen – сбросить кэш и повторить поиск\n"
            "/lang ru – сменить язык\n"
            "/reset – сбросить фильтры\n"
            "/help – эта справка"
        ),
        "startup": (
            "🤖 Бот по поиску квартир запущен!\n\n"
            "Отслеживаю {count} немецких сайтов недвижимости.\n"
            "Отправьте /help для списка команд."
        ),
    },
}
