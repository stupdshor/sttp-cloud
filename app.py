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
    user_id = message.from_user.id
    is_admin = False

    # Проверяем, админ ли это, через сервер
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/check-user", json={"user_id": user_id}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    is_admin = data.get("is_admin", False)
    except Exception as e:
        print(f"Ошибка проверки статуса: {e}")

    # Создаем кнопку
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Открыть STTP SHOP", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])

    # Приветствие в зависимости от роли
    if is_admin:
        greeting = f"Привет, {message.from_user.first_name}! 👋\nВы вошли как **Администратор**.\nНажмите кнопку, чтобы управлять магазином:"
    else:
        greeting = f"Привет, {message.from_user.first_name}! 👋\nДобро пожаловать в магазин STTP.\nНажмите кнопку, чтобы открыть каталог:"

    await message.answer(greeting, reply_markup=keyboard, parse_mode="Markdown")

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
    # Запускаем Flask в отдельном потоке, чтобы Render не выдавал ошибку "No open ports"
    t = Thread(target=run_flask)
    t.start()
    # Запускаем бота
    asyncio.run(main())
