from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import sqlite3
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Инициализация БД ---
def init_db():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    # Таблица товаров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            brand TEXT,
            price REAL,
            stock INTEGER,
            type TEXT
        )
    ''')
    
    # Таблица администраторов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    # Добавим тестовый товар, если база пустая
    cursor.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES ('Персиковый йогурт', 'Annima', 22.0, 10, 'Жидкость')")
    
    conn.commit()
    conn.close()

init_db()

# --- Модели данных ---
class OrderItem(BaseModel):
    product_id: int
    quantity: int

class Order(BaseModel):
    items: List[OrderItem]
    name: str
    phone: str

class AdminRequest(BaseModel):
    user_id: int
    owner_id: int # ID владельца бота (для проверки прав)

# --- API Эндпоинты ---

# 1. Получить все товары
@app.get("/api/products")
def get_products():
    conn = sqlite3.connect('shop.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# 2. Добавить товар
@app.post("/api/products")
def add_product(title: str, brand: str, price: float, stock: int, type: str):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES (?, ?, ?, ?, ?)", (title, brand, price, stock, type))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Товар добавлен"}

# 3. Оформить заказ (списание остатков)
@app.post("/api/order")
def create_order(order: Order):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    for item in order.items:
        cursor.execute("SELECT stock FROM products WHERE id = ?", (item.product_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Товар с ID {item.product_id} не найден")
        if row[0] < item.quantity:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Товара {item.product_id} недостаточно на складе")
        
        cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item.quantity, item.product_id))
    
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Заказ оформлен, остатки списаны"}

# --- Управление админами ---

# 4. Проверить, является ли пользователь админом
@app.get("/api/check-admin/{user_id}")
def check_admin(user_id: int):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
    is_admin = cursor.fetchone() is not None
    conn.close()
    return {"is_admin": is_admin}

# 5. Назначить админа
@app.post("/api/add-admin")
def add_admin(req: AdminRequest):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (req.user_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Пользователь {req.user_id} теперь админ"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
