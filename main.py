import asyncio
import json
import logging
import pprint

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton
)

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


class CurrencyStateGroup(StatesGroup):

    """Состояние для получения количества валюты для конвертации"""

    currency = State()
    count = State()


@dp.message(CommandStart())
async def start(message: Message):

    user_id = message.from_user.id
    username = message.from_user.username

    db_sess = db_session.create_session()

    # Проверка на нового юзера
    users = [user[0] for user in db_sess.query(User.username).filter().all()]
    if username not in users:

        # Запись пользователя в базу
        user = User()
        user.id = user_id
        user.username = username
        user.last_pairs = ""
        db_sess.add(user)

    await message.answer(
        "Сосал?"
    )

    db_sess.commit()


@dp.message(Command('last_pairs'))
async def user_last_pairs(message: Message):

    user_id = message.from_user.id

    # Создание сессии базы данных
    db_sess = db_session.create_session()

    # Получение последних валютных пар пользователя
    user = db_sess.query(User).filter(User.id == user_id).first()
    last_pairs = user.last_pairs.split(', ') if user.last_pairs else []

    keyboard = ReplyKeyboardBuilder()

    for pair in last_pairs:

        button = KeyboardButton(
            text=pair
        )

        keyboard.add(button)

    await message.answer(
        f"Ваши последние пары валют:\n{'\n'.join(last_pairs)}",
        reply_markup=keyboard.as_markup(resize_keyboard=True)
    )


@dp.message(CurrencyStateGroup.count)
async def handle_currency_count(message: Message, state: FSMContext):

    if not message.text.isdigit():
        await message.answer("Введите корректное значение валюты")
        await state.set_state(CurrencyStateGroup.count)
        return
    else:
        count = float(message.text)

    data = await state.get_data()
    currency = data['currency']
    target = data['target']
    rates = data['rates']

    # Завершение состояния
    await state.clear()

    await message.answer(f"{count} {currency} = {rates[target] * count} {target}")


@dp.message(Command('convert'))
async def convert(message: Message, state: FSMContext):

    keyboard = ReplyKeyboardRemove()

    await message.answer("Введите пару валют в формате RUB/EUR", reply_markup=keyboard)

    await state.set_state(CurrencyStateGroup.currency)


@dp.message(CurrencyStateGroup.currency)
async def change(message: Message, state: FSMContext):

    """Основная обработка валют"""

    user_id = message.from_user.id

    # Извлечение валют
    try:
        currency, target = message.text.upper().split('/')
    except ValueError:
        await message.answer("Неверный формат валют!")
        return

    # Получение актуальных курсов валют из API
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

    # Создание сессии базы данных
    db_sess = db_session.create_session()

    pair = message.text.upper()

    # Получение последних валютных пар пользователя
    user = db_sess.query(User).filter(User.id == user_id).first()
    last_pairs = user.last_pairs.split(', ') if user.last_pairs else []
    last_pairs.append(pair)

    if len(last_pairs) > 5:
        last_pairs = last_pairs[1:]

    # Чистка списка от повторений
    last_pairs = list(set(last_pairs))

    user.last_pairs = ', '.join(last_pairs)

    db_sess.commit()

    await state.set_state(CurrencyStateGroup.count)
    await state.set_data(dict(
        currency=currency,
        target=target,
        rates=response_json['conversion_rates']
    ))

    await message.answer(
        f"Введите количество валюты:"
    )


async def main():

    db_session.global_init("db/users.db")
    print("bot polling")

    await dp.start_polling(
        bot,
        skip_updates=True
    )


if __name__ == '__main__':
    asyncio.run(main())
