from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚪 Rooms", callback_data="menu_rooms"),
                InlineKeyboardButton(text="💰 Price", callback_data="menu_price"),
            ],
            [
                InlineKeyboardButton(text="📐 Area", callback_data="menu_area"),
                InlineKeyboardButton(text="📋 Status", callback_data="menu_status"),
            ],
            [
                InlineKeyboardButton(text="👁 Show filter", callback_data="show_filter"),
                InlineKeyboardButton(text="🔄 Reset", callback_data="reset_filter"),
            ],
            [
                InlineKeyboardButton(
                    text="👤 My Profile", callback_data="profile_start"
                ),
                InlineKeyboardButton(
                    text="🔗 Link Extension", callback_data="link_extension"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎓 Student/Senior", callback_data="menu_special_content"
                ),
            ],
            [
                InlineKeyboardButton(text="⏸ Pause", callback_data="pause"),
                InlineKeyboardButton(text="▶️ Resume", callback_data="resume"),
            ],
            [
                InlineKeyboardButton(text="🌐 EN", callback_data="lang_en"),
                InlineKeyboardButton(text="🌐 RU", callback_data="lang_ru"),
            ],
        ]
    )


def rooms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1–2", callback_data="rooms_1_2"),
                InlineKeyboardButton(text="2–3", callback_data="rooms_2_3"),
                InlineKeyboardButton(text="1–3", callback_data="rooms_1_3"),
            ],
            [
                InlineKeyboardButton(text="3–4", callback_data="rooms_3_4"),
                InlineKeyboardButton(text="4+", callback_data="rooms_4_99"),
            ],
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_menu")],
        ]
    )


def price_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="≤500€", callback_data="price_0_500"),
                InlineKeyboardButton(text="≤700€", callback_data="price_0_700"),
                InlineKeyboardButton(text="≤900€", callback_data="price_0_900"),
            ],
            [
                InlineKeyboardButton(text="200–550€", callback_data="price_200_550"),
                InlineKeyboardButton(text="300–650€", callback_data="price_300_650"),
                InlineKeyboardButton(text="500–1200€", callback_data="price_500_1200"),
            ],
            [
                InlineKeyboardButton(
                    text="1000–1500€", callback_data="price_1000_1500"
                ),
                InlineKeyboardButton(
                    text="1200–2000€", callback_data="price_1200_2000"
                ),
            ],
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_menu")],
        ]
    )


def area_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="≤30m²", callback_data="area_0_30"),
                InlineKeyboardButton(text="≤45m²", callback_data="area_0_45"),
                InlineKeyboardButton(text="≤60m²", callback_data="area_0_60"),
            ],
            [
                InlineKeyboardButton(text="20–50m²", callback_data="area_20_50"),
                InlineKeyboardButton(text="45–70m²", callback_data="area_45_70"),
                InlineKeyboardButton(text="60–90m²", callback_data="area_60_90"),
            ],
            [
                InlineKeyboardButton(text="70–100m²", callback_data="area_70_100"),
                InlineKeyboardButton(text="90m²+", callback_data="area_90_999"),
            ],
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_menu")],
        ]
    )


def status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 Any", callback_data="status_any"),
                InlineKeyboardButton(text="📜 WBS", callback_data="status_wbs"),
                InlineKeyboardButton(text="💼 Market", callback_data="status_market"),
            ],
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_menu")],
        ]
    )


def special_content_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Show", callback_data="special_content:on"),
                InlineKeyboardButton(text="Hide", callback_data="special_content:off"),
            ],
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_menu")],
        ]
    )


def listing_action_keyboard(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Link", callback_data=f"fill_submit:{listing_id}"
                ),
            ]
        ]
    )


def listing_link_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Link", url=url),
            ]
        ]
    )


def profile_salutation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Frau", callback_data="profile_salutation:Frau"
                ),
                InlineKeyboardButton(
                    text="Herr", callback_data="profile_salutation:Herr"
                ),
            ]
        ]
    )


def profile_income_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="100", callback_data="profile_income:100"),
                InlineKeyboardButton(text="140", callback_data="profile_income:140"),
                InlineKeyboardButton(text="160", callback_data="profile_income:160"),
            ],
            [
                InlineKeyboardButton(text="180", callback_data="profile_income:180"),
                InlineKeyboardButton(text="220", callback_data="profile_income:220"),
            ],
        ]
    )


def profile_wbs_available_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Ja", callback_data="profile_wbs_available:true"
                ),
                InlineKeyboardButton(
                    text="Nein", callback_data="profile_wbs_available:false"
                ),
            ]
        ]
    )


def profile_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Edit", callback_data="profile_edit"),
                InlineKeyboardButton(text="Save", callback_data="profile_save"),
            ],
            [InlineKeyboardButton(text="Back", callback_data="back_menu")],
        ]
    )
