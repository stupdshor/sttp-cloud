import asyncio
import logging
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = "https://sttp-cloud.vercel.app"
OWNER_ID = 1340303313  # Твой ID

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
    
    # Жесткая проверка только по ID
    if message.from_user.id == OWNER_ID:
        text = f"Привет, {message.from_user.first_name}! 👋\nВы вошли как **Владелец**.\n\nДля управления админами: /admin_panel"
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer(f"Привет, {message.from_user.first_name}! 👋", reply_markup=keyboard)

@dp.message(Command("admin_panel"))
async def cmd_admin_panel(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ У вас нет прав.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Удалить админа", callback_data="remove_admin")]
    ])
    await message.answer("Панель управления:", reply_markup=keyboard)

# Заглушки для кнопок (чтобы не было ошибок)
@dp.callback_query(F.data == "add_admin")
async def add_admin_cb(callback: types.CallbackQuery):
    if callback.from_user.id == OWNER_ID:
        await callback.answer("Функция в разработке", show_alert=True)

@dp.callback_query(F.data == "remove_admin")
async def remove_admin_cb(callback: types.CallbackQuery):
    if callback.from_user.id == OWNER_ID:
        await callback.answer("Функция в разработке", show_alert=True)

async def main():
    print("БОТ ЗАПУЩЕН С НОВЫМ КОДОМ!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    asyncio.run(main())
