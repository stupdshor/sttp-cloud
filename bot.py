import asyncio
import logging
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import aiohttp

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = "https://sttp-cloud.vercel.app"
API_URL = "https://sttp-api-new.onrender.com/api"
OWNER_ID = 1340303313  # Твой ID

# --- Flask для Render ---
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
    user_id = message.from_user.id
    is_admin = False

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/check-user", json={"user_id": user_id}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    is_admin = data.get("is_admin", False)
    except Exception as e:
        print(f"Ошибка проверки статуса: {e}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Открыть STTP SHOP", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])

    if user_id == OWNER_ID:
        greeting = f"Привет, {message.from_user.first_name}! 👋\nВы вошли как **Владелец**.\n\nДля управления админами напишите /admin_panel"
    elif is_admin:
        greeting = f"Привет, {message.from_user.first_name}! 👋\nВы вошли как **Администратор**."
    else:
        greeting = f"Привет, {message.from_user.first_name}! 👋\nДобро пожаловать в магазин STTP."

    await message.answer(greeting, reply_markup=keyboard, parse_mode="Markdown")

# --- ПАНЕЛЬ ВЛАДЕЛЬЦА ---
@dp.message(Command("admin_panel"))
async def cmd_admin_panel(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ У вас нет прав.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Удалить админа", callback_data="remove_admin")]
    ])
    await message.answer("Панель управления администраторами:", reply_markup=keyboard)

# --- ДОБАВЛЕНИЕ / УДАЛЕНИЕ (ОБРАБОТЧИКИ) ---
@dp.callback_query(F.data == "add_admin")
async def add_admin_cb(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text("Отправьте ID пользователя, которого хотите сделать админом:")

@dp.callback_query(F.data == "remove_admin")
async def remove_admin_cb(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text("Отправьте ID пользователя, которого хотите удалить из админов:")

# --- ЗАПУСК ---
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    asyncio.run(main())
