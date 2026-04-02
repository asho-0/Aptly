import typing as t

import asyncio

from app.db.session import db
from app.core.apartment import ApartmentFilter
from app.db.services import UserService, FilterService


class FilterStore:
    def __init__(
        self,
        chat_id: str,
        initial_filter: ApartmentFilter,
        initial_paused: bool,
        initial_lang: str = "en",
        initial_show_special_listings: bool = False,
    ):
        self._chat_id = chat_id
        self._filter = initial_filter
        self._paused = initial_paused
        self._show_special_listings = initial_show_special_listings
        self._lang = initial_lang
        self._filter_svc = FilterService()
        self._user_svc = UserService()

    async def _persist(self):
        async with db.session_context():
            await self._filter_svc.save_filter(
                self._chat_id,
                self._filter,
                self._paused,
                lang=self._lang,
            )

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        asyncio.create_task(self._persist())

    def set_lang(self, lang: str) -> None:
        self._lang = lang
        asyncio.create_task(self._persist_lang())

    @property
    def lang(self) -> str:
        return self._lang

    @property
    def current_filter(self) -> ApartmentFilter:
        return self._filter

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def show_special_listings(self) -> bool:
        return self._show_special_listings

    def set_show_special_listings(self, enabled: bool) -> None:
        self._show_special_listings = enabled
        asyncio.create_task(self._persist_show_special_listings())

    def reset_to_defaults(self) -> None:
        self._filter = self._filter_svc.build_default_filter()
        asyncio.create_task(self._persist())

    async def _persist_lang(self) -> None:
        async with db.session_context():
            await self._user_svc.update_language(self._chat_id, self._lang)

    async def _persist_show_special_listings(self) -> None:
        async with db.session_context():
            await self._user_svc.update_show_special_listings(
                self._chat_id,
                self._show_special_listings,
            )


class UserRegistry:
    def __init__(self) -> None:
        self._stores: dict[str, FilterStore] = {}
        self._lock = asyncio.Lock()
        self.extension_gateway = None

    async def get_or_create(
        self,
        chat_id: str,
        username: t.Optional[str] = None,
        full_name: t.Optional[str] = None,
    ) -> FilterStore:
        async with self._lock:
            if chat_id in self._stores:
                return self._stores[chat_id]

            async with db.session_context():
                user_svc = UserService()
                user = await user_svc.get_or_register_user(chat_id, username, full_name)

                domain_filter = user_svc.convert_to_domain(user.filters)
                lang = (
                    user.language
                    if isinstance(getattr(user, "language", None), str)
                    and user.language
                    else getattr(user.filters, "lang", None) or "en"
                )
                store = FilterStore(
                    chat_id,
                    domain_filter,
                    user.filters.paused,
                    lang,
                    bool(user.show_special_listings),
                )

                self._stores[chat_id] = store
                return store

    async def fetch_all_active(self) -> list[tuple[str, FilterStore]]:
        async with db.session_context():
            user_svc = UserService()
            users = await user_svc.repo.get_all_active_users()

            for user in users:
                if user.chat_id not in self._stores:
                    domain_filter = user_svc.convert_to_domain(user.filters)
                    lang = (
                        user.language
                        if isinstance(getattr(user, "language", None), str)
                        and user.language
                        else getattr(user.filters, "lang", None) or "en"
                    )
                    self._stores[user.chat_id] = FilterStore(
                        user.chat_id,
                        domain_filter,
                        user.filters.paused,
                        lang,
                        bool(user.show_special_listings),
                    )
        return list(self._stores.items())
