import asyncio
import typing as t

from app.core.apartment import ApartmentFilter
from app.db.session import db
from app.db.services import UserService, FilterService

class FilterStore:
    def __init__(
        self,
        chat_id: str,
        initial_filter: ApartmentFilter,
        initial_paused: bool,
    ):
        self._chat_id = chat_id
        self._filter = initial_filter
        self._paused = initial_paused
        self._filter_svc = FilterService()

    async def _persist(self):
        async with db.session_context():
            await self._filter_svc.save_filter(
                self._chat_id, 
                self._filter, 
                self._paused
            )

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        asyncio.create_task(self._persist())

    @property
    def current_filter(self) -> ApartmentFilter:
        return self._filter

    @property
    def is_paused(self) -> bool:
        return self._paused
    
    def reset_to_defaults(self) -> None:
        self._filter = self._filter_svc.build_default_filter()
        asyncio.create_task(self._persist())


class UserRegistry:
    def __init__(self) -> None:
        self._stores: dict[str, FilterStore] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self, 
        chat_id: str, 
        username: t.Optional[str] = None, 
        full_name: t.Optional[str] = None
    ) -> FilterStore:
        async with self._lock:
            if chat_id in self._stores:
                return self._stores[chat_id]

            async with db.session_context():
                user_svc = UserService()
                user = await user_svc.get_or_register_user(chat_id, username, full_name)
                
                domain_filter = user_svc.convert_to_domain(user.filter)
                store = FilterStore(chat_id, domain_filter, user.filter.paused)
                
                self._stores[chat_id] = store
                return store
    
    async def fetch_all_active(self) -> t.List[t.Tuple[str, FilterStore]]:
        async with db.session_context():
            user_svc = UserService()
            users = await user_svc.repo.get_all_active_users()
            
            for user in users:
                if user.chat_id not in self._stores:
                    domain_filter = user_svc.convert_to_domain(user.filter)
                    self._stores[user.chat_id] = FilterStore(
                        user.chat_id, domain_filter, user.filter.paused
                    )
        return list(self._stores.items())