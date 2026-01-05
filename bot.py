import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, Location
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import asyncpg

# ===== Настройки =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# ===== FSM States =====
class AddSpot(StatesGroup):
    location = State()
    bonus = State()
    comment = State()

# ===== Инициализация =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ===== Команды =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я помогу отслеживать точки с высокими бонусами в Yandex Delivery.\n\n"
        "Используй /add, чтобы добавить новую точку."
    )

@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    await message.answer("📍 Отправьте свою геопозицию (в момент получения заказа).")
    await state.set_state(AddSpot.location)

@dp.message(AddSpot.location)
async def process_location(message: Message, state: FSMContext):
    if message.location:
        await state.update_data(
            latitude=message.location.latitude,
            longitude=message.location.longitude
        )
        await message.answer("💰 Введите размер бонуса в BYN (только число, например: 12):")
        await state.set_state(AddSpot.bonus)
    else:
        await message.answer("Пожалуйста, отправьте геопозицию через 📎 → Геопозиция.")

@dp.message(AddSpot.bonus)
async def process_bonus(message: Message, state: FSMContext):
    try:
        bonus = float(message.text.replace(',', '.'))
        if bonus < 0:
            raise ValueError
        await state.update_data(bonus_byn=bonus)
        await message.answer("✏️ (Опционально) Напишите комментарий (например: 'пятница вечер', 'дождь') или нажмите /skip:")
        await state.set_state(AddSpot.comment)
    except (ValueError, AttributeError):
        await message.answer("Пожалуйста, введите корректное число (например: 12 или 15.5).")

@dp.message(AddSpot.comment)
async def process_comment(message: Message, state: FSMContext):
    comment = message.text if message.text != "/skip" else ""
    data = await state.get_data()

    # Сохранение в базу
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        """
        INSERT INTO hot_spots (user_id, latitude, longitude, bonus_byn, comment, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        message.from_user.id,
        data["latitude"],
        data["longitude"],
        data["bonus_byn"],
        comment,
        datetime.utcnow()
    )
    await conn.close()

    await message.answer(f"✅ Сохранено!\nБонус: {data['bonus_byn']} BYN\nКоординаты: {data['latitude']:.4f}, {data['longitude']:.4f}")
    await state.clear()

@dp.message(Command("skip"))
async def skip_comment(message: Message, state: FSMContext):
    await process_comment(message, state)

# ===== Запуск =====
async def create_table():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS hot_spots (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            bonus_byn DOUBLE PRECISION NOT NULL,
            comment TEXT,
            timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
        )
    """)
    await conn.close()

async def main():
    await create_table()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
