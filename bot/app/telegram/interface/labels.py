FILTER_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "header": "📊 Active filters:",
        "rooms": "🚪 Rooms",
        "area": "📐 Area",
        "price": "💰 Price",
        "status": "📋 Status",
        "sqm_unit": "m²",
        "price_unit": "€/mo",
        "none": "–",
        "special_content": "🎓 Student/Senior",
        "special_on": "shown",
        "special_off": "hidden",
    },
    "ru": {
        "header": "📊 Активные фильтры:",
        "rooms": "🚪 Комнаты",
        "area": "📐 Площадь",
        "price": "💰 Цена",
        "status": "📋 Статус",
        "sqm_unit": "м²",
        "price_unit": "€/мес",
        "none": "–",
        "special_content": "🎓 Студенты/Пенсионеры",
        "special_on": "показывать",
        "special_off": "скрывать",
    },
}


APARTMENT_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "address": "📍 Address:",
        "district": "🏙 District:",
        "rooms": "🚪 Rooms:",
        "area": "📐 Area:",
        "cold_rent": "🧊 Kaltmiete:",
        "extra_costs": "🔌 Nebenkosten:",
        "total_rent": "💵 Gesamtmiete:",
        "wbs_yes": "✅ required",
        "wbs_no": "❌ not required",
        "wbs_label": "📜 WBS:",
        "floor": "🏢 Etage:",
        "published": "🕒 Published:",
        "area_unit": "m²",
    },
    "ru": {
        "address": "📍 Адрес:",
        "district": "🏙 Район:",
        "rooms": "🚪 Комнат:",
        "area": "📐 Площадь:",
        "cold_rent": "🧊 Холодная аренда:",
        "extra_costs": "🔌 Небенкостен:",
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
        "menu_title": "⚙️ Use the buttons below to configure your filter and extension:",
        "choose_rooms": "🚪 Select room range:",
        "choose_price": "💰 Select price range:",
        "choose_area": "📐 Select area range:",
        "choose_status": "📋 Select social status:",
        "choose_special_content": "🎓 Do you want to see student/senior apartments?",
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
        "profile_intro": "👤 Complete your profile. Use buttons where choices are limited.",
        "profile_menu_title": "👤 My Profile",
        "profile_current": (
            "Current profile:\n"
            "Salutation: {salutation}\n"
            "First name: {first_name}\n"
            "Last name: {last_name}\n"
            "Email: {email}\n"
            "Phone: {phone}\n"
            "Street: {street}\n"
            "House number: {house_number}\n"
            "ZIP code: {zip_code}\n"
            "City: {city}\n"
            "Persons total: {persons_total}\n"
            "WBS available: {wbs_available}\n"
            "WBS valid until: {wbs_date}\n"
            "WBS rooms: {wbs_rooms}\n"
            "WBS income: {wbs_income}"
        ),
        "profile_prompt_salutation": "Choose your salutation:",
        "profile_prompt_first_name": "Enter your first name:",
        "profile_prompt_last_name": "Enter your last name:",
        "profile_prompt_email": "Enter your email:",
        "profile_prompt_phone": "Enter your phone number:",
        "profile_prompt_street": "Enter your street name:",
        "profile_prompt_house_number": "Enter your house number:",
        "profile_prompt_zip_code": "Enter your ZIP code:",
        "profile_prompt_city": "Enter your city:",
        "profile_prompt_persons_total": "Enter total persons count:",
        "profile_prompt_wbs_available": "Do you have a WBS?",
        "profile_prompt_wbs_date": "Enter your WBS valid-until date in YYYY-MM-DD format:",
        "profile_prompt_wbs_rooms": "Enter your WBS rooms count from 1 to 7:",
        "profile_prompt_wbs_income": "Choose your WBS income limit:",
        "profile_saved": "✅ Profile saved.",
        "profile_synced": "✅ Profile synced to extension.",
        "profile_invalid": "⚠️ Value cannot be empty.",
        "profile_invalid_number": "⚠️ Enter a valid number.",
        "profile_invalid_date": "⚠️ Use the YYYY-MM-DD format.",
        "profile_incomplete": "⚠️ Complete your profile from the menu first.",
        "pairing_pin": "🔗 Pairing PIN: <code>{pin}</code>\nValid for 5 minutes.",
        "listing_processing": "⏳ Processing...",
        "listing_submitted": "✅ Submitted",
        "extension_unavailable": "⚠️ Extension is not connected.",
        "listing_missing": "⚠️ Listing was not found.",
        "special_content_enabled": "✅ Student/senior apartments are enabled.",
        "special_content_disabled": "✅ Student/senior apartments are hidden.",
    },
    "ru": {
        "menu_title": "⚙️ Используйте кнопки ниже для настройки фильтра и расширения:",
        "choose_rooms": "🚪 Выберите количество комнат:",
        "choose_price": "💰 Выберите диапазон цены:",
        "choose_area": "📐 Выберите диапазон площади:",
        "choose_status": "📋 Выберите тип жилья:",
        "choose_special_content": "🎓 Показывать квартиры для студентов/пенсионеров?",
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
        "profile_intro": "👤 Заполните профиль. Для ограниченных полей используйте кнопки.",
        "profile_menu_title": "👤 Мой профиль",
        "profile_current": (
            "Текущий профиль:\n"
            "Обращение: {salutation}\n"
            "Имя: {first_name}\n"
            "Фамилия: {last_name}\n"
            "Email: {email}\n"
            "Телефон: {phone}\n"
            "Улица: {street}\n"
            "Номер дома: {house_number}\n"
            "Индекс: {zip_code}\n"
            "Город: {city}\n"
            "Всего человек: {persons_total}\n"
            "WBS есть: {wbs_available}\n"
            "WBS действует до: {wbs_date}\n"
            "Комнат WBS: {wbs_rooms}\n"
            "Доход WBS: {wbs_income}"
        ),
        "profile_prompt_salutation": "Выберите обращение:",
        "profile_prompt_first_name": "Введите имя:",
        "profile_prompt_last_name": "Введите фамилию:",
        "profile_prompt_email": "Введите email:",
        "profile_prompt_phone": "Введите телефон:",
        "profile_prompt_street": "Введите улицу:",
        "profile_prompt_house_number": "Введите номер дома:",
        "profile_prompt_zip_code": "Введите почтовый индекс:",
        "profile_prompt_city": "Введите город:",
        "profile_prompt_persons_total": "Введите общее количество человек:",
        "profile_prompt_wbs_available": "У вас есть WBS?",
        "profile_prompt_wbs_date": "Введите дату действия WBS в формате YYYY-MM-DD:",
        "profile_prompt_wbs_rooms": "Введите количество комнат WBS от 1 до 7:",
        "profile_prompt_wbs_income": "Выберите лимит дохода WBS:",
        "profile_saved": "✅ Профиль сохранён.",
        "profile_synced": "✅ Профиль синхронизирован с расширением.",
        "profile_invalid": "⚠️ Значение не может быть пустым.",
        "profile_invalid_number": "⚠️ Введите корректное число.",
        "profile_invalid_date": "⚠️ Используйте формат YYYY-MM-DD.",
        "profile_incomplete": "⚠️ Сначала заполните профиль через меню.",
        "pairing_pin": "🔗 PIN для привязки: <code>{pin}</code>\nДействует 5 минут.",
        "listing_processing": "⏳ Processing...",
        "listing_submitted": "✅ Submitted",
        "extension_unavailable": "⚠️ Расширение не подключено.",
        "listing_missing": "⚠️ Объявление не найдено.",
        "special_content_enabled": "✅ Квартиры для студентов/пенсионеров включены.",
        "special_content_disabled": "✅ Квартиры для студентов/пенсионеров скрыты.",
    },
}
