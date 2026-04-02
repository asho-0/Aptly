import datetime
import secrets
from dataclasses import dataclass

from sqlalchemy import delete, select, update

from app.core.config import settings
from app.db.models.models import ExtensionPairing, User
from app.db.session import db


@dataclass
class PairingResult:
    chat_id: str
    token: str


class PairingStore:
    async def create_pin(self, chat_id: str) -> str:
        await self._cleanup()
        pin = await self._generate_pin()
        expires_at = self._utc_now() + datetime.timedelta(
            seconds=settings.PAIRING_PIN_TTL_SECONDS
        )

        async with db.session_context() as session:
            await session.execute(
                delete(ExtensionPairing).where(ExtensionPairing.chat_id == chat_id)
            )
            await session.execute(
                update(User).where(User.chat_id == chat_id).values(pairing_pin=pin)
            )
            session.add(
                ExtensionPairing(
                    chat_id=chat_id,
                    pin_code=pin,
                    pin_expires_at=expires_at,
                )
            )

        return pin

    async def consume_pin(self, pin: str) -> PairingResult | None:
        await self._cleanup()
        now = self._utc_now()

        async with db.session_context() as session:
            result = await session.execute(
                select(ExtensionPairing).where(
                    ExtensionPairing.pin_code == pin,
                    ExtensionPairing.pin_expires_at > now,
                    ExtensionPairing.consumed_at.is_(None),
                )
            )
            pairing = result.scalar_one_or_none()
            if pairing is None:
                return None

            pairing.token = secrets.token_urlsafe(32)
            pairing.token_expires_at = now + datetime.timedelta(
                seconds=settings.EXTENSION_TOKEN_TTL_SECONDS
            )
            pairing.consumed_at = now
            await session.execute(
                update(User)
                .where(User.chat_id == pairing.chat_id)
                .values(pairing_pin=None)
            )
            return PairingResult(chat_id=pairing.chat_id, token=pairing.token or "")

    async def resolve_token(self, token: str) -> str | None:
        await self._cleanup()
        now = self._utc_now()

        async with db.session_context() as session:
            result = await session.execute(
                select(ExtensionPairing.chat_id).where(
                    ExtensionPairing.token == token,
                    ExtensionPairing.token_expires_at.is_not(None),
                    ExtensionPairing.token_expires_at > now,
                )
            )
            return result.scalar_one_or_none()

    async def _cleanup(self) -> None:
        now = self._utc_now()
        async with db.session_context() as session:
            await session.execute(
                delete(ExtensionPairing).where(
                    ExtensionPairing.pin_expires_at <= now,
                    ExtensionPairing.token_expires_at.is_(None),
                )
            )
            await session.execute(
                delete(ExtensionPairing).where(
                    ExtensionPairing.token_expires_at.is_not(None),
                    ExtensionPairing.token_expires_at <= now,
                )
            )

    async def _generate_pin(self) -> str:
        while True:
            pin = f"{secrets.randbelow(1_000_000):06d}"
            async with db.session_context() as session:
                result = await session.execute(
                    select(ExtensionPairing.id).where(ExtensionPairing.pin_code == pin)
                )
                if result.scalar_one_or_none() is None:
                    return pin

    @staticmethod
    def _utc_now() -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
