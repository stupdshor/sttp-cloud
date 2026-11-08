import asyncio
import logging
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = "https://sttp-cloud.vercel.app"
OWNER_ID = 1340303313

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Открыть STTP SHOP", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    
    if message.from_user.id == OWNER_ID:
        text = f"Привет, {message.from_user.first_name}!\nВы вошли как Владелец.\n/admin_panel — Управление админами"
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(f"Привет, {message.from_user.first_name}!", reply_markup=keyboard)

@dp.message(Command("admin_panel"))
async def cmd_admin_panel(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Удалить админа", callback_data="remove_admin")]
    ])
    await message.answer("Панель управления:", reply_markup=keyboard)

async def main():
    print("БОТ ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    asyncio.run(main())
