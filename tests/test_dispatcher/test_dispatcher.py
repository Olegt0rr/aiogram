import datetime

import pytest

from aiogram import Bot
from aiogram.api.types import Message, Update, Chat, User
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.dispatcher.router import Router


class TestDispatcher:
    def test_parent_router(self):
        dp = Dispatcher()
        with pytest.raises(RuntimeError):
            dp.parent_router = Router()
        assert dp.parent_router is None
        dp._parent_router = Router()
        assert dp.parent_router is None

    @pytest.mark.asyncio
    async def test_feed_update(self):
        dp = Dispatcher()
        bot = Bot("TOKEN")

        @dp.message_handler()
        async def my_handler(message: Message, **kwargs):
            assert "bot" in kwargs
            assert isinstance(kwargs["bot"], Bot)
            assert kwargs["bot"] == bot
            return message.text

        results_count = 0
        async for result in dp.feed_update(
            bot=bot,
            update=Update(
                update_id=42,
                message=Message(
                    message_id=42,
                    date=datetime.datetime.now(),
                    text="test",
                    chat=Chat(id=42, type="private"),
                    from_user=User(id=42, is_bot=False, first_name="Test"),
                ),
            ),
        ):
            results_count += 1
            assert result == "test"

        assert results_count == 1

    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_listen_updates(self):
        pass

    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_polling(self):
        pass