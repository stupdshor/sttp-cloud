import asyncio
import logging
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import aiohttp

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = "https://sttp-cloud.vercel.app"
API_URL = "https://sttp-api-new.onrender.com/api"
OWNER_ID = 1340303313

# --- Flask для Render (чтобы сервис не засыпал) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- Логика Бота ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Открыть STTP SHOP", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer(f"Привет, {message.from_user.first_name}! 👋", reply_markup=keyboard)

@dp.message(Command("makeadmin"))
async def cmd_make_admin(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ У вас нет прав.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: /makeadmin <ID>")
        return
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/add-admin", json={"user_id": int(args[1]), "owner_id": OWNER_ID}) as resp:
            if resp.status == 200:
                await message.answer("✅ Готово!")
            else:
                await message.answer("❌ Ошибка")

@dp.message(Command("removeadmin"))
async def cmd_remove_admin(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        return
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/remove-admin", json={"user_id": int(args[1]), "owner_id": OWNER_ID}) as resp:
            if resp.status == 200:
                await message.answer("🗑 Пользователь удален из админов.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    t = Thread(target=run_flask)
    t.start()
    # Запускаем бота
    asyncio.run(main())