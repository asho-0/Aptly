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
        "menu_title": "⚙️ Use the buttons below to configure your filter:",
        "choose_rooms": "🚪 Select room range:",
        "choose_price": "💰 Select price range:",
        "choose_area": "📐 Select area range:",
        "choose_status": "📋 Select social status:",
        "filter_updated": "✅ Filter updated!",
        "filter_incomplete": "⚠️ Please set all filter fields before searching.",
        "preview_searching": "🔍 Searching current listings with your new filter…",
        "preview_none": "📭 No matching listings found right now. You'll be notified when new ones appear.",
        "paused": "⏸ Notifications paused.",
        "resumed": "▶️ Notifications resumed!",
        "reset_done": "🔄 Filters reset to defaults.",
        "invalid_value": "⚠️ Invalid value.",
        "status_options": "Valid options: any | market | wbs",
        "lang_changed": "🌐 Language set to English.",
        "lang_invalid": "⚠️ Supported languages: en, ru",
        "startup": (
            "🤖 Apartment Notifier started!\n\n"
            "Monitoring {count} German real-estate sources.\n"
            "Send /help to open the menu."
        ),
    },
    "ru": {
        "menu_title": "⚙️ Используйте кнопки ниже для настройки фильтра:",
        "choose_rooms": "🚪 Выберите количество комнат:",
        "choose_price": "💰 Выберите диапазон цены:",
        "choose_area": "📐 Выберите диапазон площади:",
        "choose_status": "📋 Выберите тип жилья:",
        "filter_updated": "✅ Фильтр обновлён!",
        "filter_incomplete": "⚠️ Пожалуйста, заполните все поля фильтра перед поиском.",
        "preview_searching": "🔍 Ищу текущие объявления с новым фильтром…",
        "preview_none": "📭 Подходящих объявлений пока нет. Вы получите уведомление, когда появятся новые.",
        "paused": "⏸ Уведомления приостановлены.",
        "resumed": "▶️ Уведомления возобновлены!",
        "reset_done": "🔄 Фильтры сброшены.",
        "invalid_value": "⚠️ Неверное значение.",
        "status_options": "Допустимые значения: any | market | wbs",
        "lang_changed": "🌐 Язык установлен: Русский.",
        "lang_invalid": "⚠️ Поддерживаемые языки: en, ru",
        "startup": (
            "🤖 Бот по поиску квартир запущен!\n\n"
            "Отслеживаю {count} немецких сайтов недвижимости.\n"
            "Отправьте /help для открытия меню."
        ),
    },
}
