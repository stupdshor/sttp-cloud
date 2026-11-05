import asyncio
import logging
import aiohttp
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Берем токен из переменных окружения (для безопасности)
BOT_TOKEN = os.getenv("BOT_TOKEN", "9028052598:AAHL2yUbEQBCLqygYfRY42K4XQ-a_nc3aYM")
WEB_APP_URL = "https://sttp-cloud.vercel.app"
API_URL = "https://sttp-api-new.onrender.com/api"
OWNER_ID = 1340303313  # <-- ВАШ ID

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Открыть STTP SHOP", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nДобро пожаловать в магазин STTP.",
        reply_markup=keyboard
    )

@dp.message(Command("makeadmin"))
async def cmd_make_admin(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: /makeadmin <ID пользователя>")
        return
    try:
        new_admin_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ ID должен быть числом.")
        return
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/add-admin", json={"user_id": new_admin_id, "owner_id": OWNER_ID}) as resp:
            if resp.status == 200:
                await message.answer(f"✅ Пользователь с ID {new_admin_id} теперь администратор!")
            else:
                await message.answer(f"❌ Ошибка. Код: {resp.status}")

@dp.message(Command("removeadmin"))
async def cmd_remove_admin(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: /removeadmin <ID пользователя>")
        return
    try:
        rem_admin_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ ID должен быть числом.")
        return
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/remove-admin", json={"user_id": rem_admin_id, "owner_id": OWNER_ID}) as resp:
            if resp.status == 200:
                await message.answer(f"🗑 Пользователь с ID {rem_admin_id} больше не администратор.")
            else:
                await message.answer(f"❌ Ошибка. Код: {resp.status}")

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")