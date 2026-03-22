import pytest
from aiogram.exceptions import TelegramAPIError
from app.telegram.notifier.notifier import TelegramNotifier
from tests.conftest import make_apartment


@pytest.fixture
def bot(mocker):
    b = mocker.AsyncMock()
    b.send_photo = mocker.AsyncMock()
    b.send_message = mocker.AsyncMock()
    return b


@pytest.fixture
def notifier(bot):
    return TelegramNotifier(bot)


class TestSendText:

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, notifier, bot):
        result = await notifier.send_text(123, "Hello")
        assert result is True
        bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_telegram_error(self, notifier, bot, mocker):
        bot.send_message.side_effect = TelegramAPIError(
            method=mocker.MagicMock(), message="error"
        )
        result = await notifier.send_text(123, "Hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_splits_long_message_into_chunks(self, notifier, bot):
        await notifier.send_text(123, "x" * 5000)
        assert bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_short_message_sent_in_one_call(self, notifier, bot):
        await notifier.send_text(123, "short")
        assert bot.send_message.call_count == 1

    @pytest.mark.asyncio
    async def test_sends_to_correct_chat_id(self, notifier, bot):
        await notifier.send_text(999, "msg")
        args, _ = bot.send_message.call_args
        assert args[0] == 999


class TestSendApartment:

    @pytest.mark.asyncio
    async def test_sends_photo_when_image_present(self, notifier, bot):
        apt = make_apartment()
        apt.image_url = "https://example.com/img.jpg"
        result = await notifier.send_apartment(123, apt, lang="en")
        assert result is True
        bot.send_photo.assert_called_once()
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_text_when_photo_fails(self, notifier, bot, mocker):
        bot.send_photo.side_effect = TelegramAPIError(
            method=mocker.MagicMock(), message="error"
        )
        apt = make_apartment()
        apt.image_url = "https://example.com/img.jpg"
        result = await notifier.send_apartment(123, apt, lang="en")
        assert result is True
        bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_text_when_no_image(self, notifier, bot):
        apt = make_apartment()
        apt.image_url = None
        result = await notifier.send_apartment(123, apt, lang="en")
        assert result is True
        bot.send_photo.assert_not_called()
        bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_text_fails(self, notifier, bot, mocker):
        bot.send_message.side_effect = TelegramAPIError(
            method=mocker.MagicMock(), message="error"
        )
        apt = make_apartment()
        apt.image_url = None
        result = await notifier.send_apartment(123, apt, lang="en")
        assert result is False

    @pytest.mark.asyncio
    async def test_caption_truncated_to_1024(self, notifier, bot):
        apt = make_apartment(title="x" * 2000)
        apt.image_url = "https://example.com/img.jpg"
        await notifier.send_apartment(123, apt, lang="en")
        _, kwargs = bot.send_photo.call_args
        assert len(kwargs.get("caption", "")) <= 1024

    @pytest.mark.asyncio
    async def test_ru_lang_produces_russian_text(self, notifier, bot):
        apt = make_apartment()
        apt.image_url = None
        await notifier.send_apartment(123, apt, lang="ru")
        args, kwargs = bot.send_message.call_args
        text = kwargs.get("text") or args[1]
        assert any(word in text for word in ["Комнат", "Адрес", "Площадь", "аренда"])

    @pytest.mark.asyncio
    async def test_en_lang_produces_english_text(self, notifier, bot):
        apt = make_apartment()
        apt.image_url = None
        await notifier.send_apartment(123, apt, lang="en")
        args, kwargs = bot.send_message.call_args
        text = kwargs.get("text") or args[1]
        assert any(word in text for word in ["Rooms", "Address", "Area", "rent"])
