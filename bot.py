import os
import asyncio
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, Location
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

import asyncpg

# === Конфигурация ===
BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

class AddSpot(StatesGroup):
    location = State()
    bonus = State()
    comment = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === Команды ===
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет! Используй /add, чтобы сохранить точку с бонусом.")

@dp.message(Command("add"))
async def add_spot(message: Message, state: FSMContext):
    await message.answer("📍 Отправьте геопозицию (в момент получения заказа).")
    await state.set_state(AddSpot.location)

@dp.message(AddSpot.location)
async def get_location(message: Message, state: FSMContext):
    if message.location:
        await state.update_data(lat=message.location.latitude, lon=message.location.longitude)
        await message.answer("💰 Введите бонус в BYN (например: 12):")
        await state.set_state(AddSpot.bonus)
    else:
        await message.answer("Пожалуйста, отправьте геопозицию через 📎 → Геопозиция.")

@dp.message(AddSpot.bonus)
async def get_bonus(message: Message, state: FSMContext):
    try:
        bonus = float(message.text.replace(',', '.'))
        await state.update_data(bonus=bonus)
        await message.answer("✏️ Комментарий (или /skip):")
        await state.set_state(AddSpot.comment)
    except ValueError:
        await message.answer("Введите число: 5, 12.5 и т.д.")

@dp.message(AddSpot.comment)
async def save_spot(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = "" if message.text == "/skip" else message.text

    # Сохраняем в PostgreSQL
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS hot_spots (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            bonus_byn DOUBLE PRECISION NOT NULL,
            comment TEXT,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    await conn.execute(
        "INSERT INTO hot_spots (user_id, latitude, longitude, bonus_byn, comment) VALUES ($1, $2, $3, $4, $5)",
        message.from_user.id,
        data["lat"],
        data["lon"],
        data["bonus"],
        comment
    )
    await conn.close()

    await message.answer(f"✅ Сохранено!\nБонус: {data['bonus']} BYN")
    await state.clear()

@dp.message(Command("skip"))
async def skip(message: Message, state: FSMContext):
    await save_spot(message, state)

# === Запуск ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
