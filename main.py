import asyncio
import json
import logging
import pprint

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

import requests

from config import TOKEN
from data import db_session
from data.users import User


bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logging.basicConfig(
    level=logging.INFO,
    filename='logs.log',
    format="%(asctime)s (%(levelname)s) %(message)s",
    encoding='utf-8'
)

aiogram_logger = logging.getLogger('aiogram')
aiogram_logger.setLevel(logging.WARNING)


@dp.message(CommandStart())
async def start(message: Message):

    user_id = message.from_user.id
    username = message.from_user.username

    # Запись пользователя в базу
    user = User()
    user.id = user_id
    user.username = username
    user.last_pairs = ""
    db_sess = db_session.create_session()
    db_sess.add(user)
    db_sess.commit()

    await message.answer(
        "Сосал?"
    )


@dp.message()
async def change(message: Message):

    # Извлечение валют
    try:
        currency, target = message.text.upper().split('/')
    except ValueError:
        await message.answer("Неверный формат валют!")
        return

    url = f"https://v6.exchangerate-api.com/v6/69dc936e8c547778eee18b82/latest/{currency}"
    response_json = requests.get(url).json()

    # Проверка на правильность ввода
    if response_json['result'] == 'error':
        await message.answer(
            f"Ошибка на стороне сервера. Тип ошибки: {response_json['error-type']}"
        )
        return

    # Проверка наличия конечной валюты в списке
    if target not in response_json['conversion_rates']:
        await message.answer(
            "К сожалению, на данный момент в эту валюту конвертировать нельзя"
        )
        return

    # ToDo: записать в бд эту пару и убрать первую если длина больше 5

    await message.answer(
        f"1 {currency} = {response_json['conversion_rates'][target]} {target}"
    )


async def main():
    db_session.global_init("db/users.db")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    asyncio.run(main())
