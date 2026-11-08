import asyncio
import logging
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
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
dp = Dispatcher(storage=MemoryStorage())

# Состояния для ввода ID
class AdminStates(StatesGroup):
    waiting_for_add_id = State()
    waiting_for_remove_id = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Кнопка магазина
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Открыть STTP SHOP", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])

    # Жесткая проверка только по ID из кода
    if user_id == OWNER_ID:
        text = (
            f"Привет, {message.from_user.first_name}! 👋\n"
            "Вы вошли как **Владелец**.\n\n"
            "Доступные команды:\n"
            "/admin_panel — Управление администраторами"
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        text = f"Привет, {message.from_user.first_name}! 👋\nДобро пожаловать в магазин STTP."
        await message.answer(text, reply_markup=keyboard)

# --- ПАНЕЛЬ ВЛАДЕЛЬЦА ---
@dp.message(Command("admin_panel"))
async def cmd_admin_panel(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Удалить админа", callback_data="remove_admin")]
    ])
    await message.answer("Панель управления администраторами:", reply_markup=keyboard)

# --- ДОБАВЛЕНИЕ АДМИНА ---
@dp.callback_query(F.data == "add_admin")
async def process_add_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    
    await callback.message.edit_text("Отправьте Telegram ID пользователя, которого хотите сделать админом:")
    await state.set_state(AdminStates.waiting_for_add_id)

@dp.message(AdminStates.waiting_for_add_id)
async def process_add_admin_id(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        new_admin_id = int(message.text)
    except ValueError:
        await message.answer("⚠️ ID должен быть числом. Попробуйте снова.")
        return

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/add-admin", json={"user_id": new_admin_id, "owner_id": OWNER_ID}) as resp:
            if resp.status == 200:
                await message.answer(f"✅ Пользователь с ID {new_admin_id} теперь администратор!")
            else:
                await message.answer(f"❌ Ошибка. Код: {resp.status}")
    
    await state.clear()

# --- УДАЛЕНИЕ АДМИНА ---
@dp.callback_query(F.data == "remove_admin")
async def process_remove_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/get-admins") as resp:
                if resp.status == 200:
                    admins = await resp.json()
                    if not admins:
                        await callback.message.edit_text("Список админов пуст.")
                        return
                    
                    text = "Текущие админы:\n" + "\n".join([f"• {id}" for id in admins])
                    text += "\n\nОтправьте ID пользователя, которого хотите удалить из админов:"
                    await callback.message.edit_text(text)
                    await state.set_state(AdminStates.waiting_for_remove_id)
                else:
                    await callback.message.edit_text("❌ Ошибка загрузки списка.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")

@dp.message(AdminStates.waiting_for_remove_id)
async def process_remove_admin_id(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        rem_admin_id = int(message.text)
    except ValueError:
        await message.answer("⚠️ ID должен быть числом. Попробуйте снова.")
        return

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/remove-admin", json={"user_id": rem_admin_id, "owner_id": OWNER_ID}) as resp:
            if resp.status == 200:
                await message.answer(f"🗑 Пользователь с ID {rem_admin_id} больше не администратор.")
            else:
                await message.answer(f"❌ Ошибка. Код: {resp.status}")
    
    await state.clear()

async def main():
    print("БОТ ЗАПУЩЕН С НОВЫМ КОДОМ!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    asyncio.run(main())
