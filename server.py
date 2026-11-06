from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import os
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Берем URL базы данных из переменных окружения Render
DATABASE_URL = os.getenv("DATABASE_URL")

# Функция подключения к базе
def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL не задан в переменных окружения!")
    # psycopg2 требует замены postgres:// на postgresql:// (иногда)
    url = DATABASE_URL.replace("postgres://", "postgresql://")
    # Подключаемся с курсором, который возвращает словари (как в sqlite3.Row)
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

# --- Инициализация БД ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Таблица товаров (AUTOINCREMENT в PostgreSQL заменяется на SERIAL)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
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
            user_id BIGINT PRIMARY KEY
        )
    ''')
    
    # Добавим тестовый товар, если база пустая
    cursor.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()['count'] == 0:
        cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES (%s, %s, %s, %s, %s)", 
                       ('Персиковый йогурт', 'Annima', 22.0, 10, 'Жидкость'))
    
    conn.commit()
    cursor.close()
    conn.close()

# Вызываем инициализацию при старте
try:
    init_db()
    print("База данных успешно инициализирована!")
except Exception as e:
    print(f"Ошибка инициализации БД: {e}")

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
    owner_id: int

class ProductRequest(BaseModel):
    title: str
    brand: str
    price: float
    stock: int
    type: str
    admin_id: int

class DeleteRequest(BaseModel):
    product_id: int
    admin_id: int

class EditRequest(BaseModel):
    product_id: int
    new_price: float
    new_stock: int
    admin_id: int

# --- API Эндпоинты ---

# 1. Получить все товары
@app.get("/api/products")
def get_products():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. Оформить заказ (списание остатков)
@app.post("/api/order")
def create_order(order: Order):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for item in order.items:
            cursor.execute("SELECT stock FROM products WHERE id = %s", (item.product_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Товар с ID {item.product_id} не найден")
            if row['stock'] < item.quantity:
                conn.close()
                raise HTTPException(status_code=400, detail=f"Товара {item.product_id} недостаточно на складе")
            
            cursor.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (item.quantity, item.product_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "message": "Заказ оформлен, остатки списаны"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Управление админами ---

# 3. Проверить, является ли пользователь админом
@app.get("/api/check-admin/{user_id}")
def check_admin(user_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE user_id = %s", (user_id,))
        is_admin = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return {"is_admin": is_admin}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. Назначить админа
@app.post("/api/add-admin")
def add_admin(req: AdminRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (req.user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "message": f"Пользователь {req.user_id} теперь админ"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 5. Удалить админа
@app.post("/api/remove-admin")
def remove_admin(req: AdminRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = %s", (req.user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "message": f"Пользователь {req.user_id} удален из админов"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Управление товарами (АДМИНКА) ---

# 6. Добавить товар
@app.post("/api/add-product")
def add_product_admin(req: ProductRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE user_id = %s", (req.admin_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=403, detail="Нет прав администратора")
        
        cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES (%s, %s, %s, %s, %s)", 
                       (req.title, req.brand, req.price, req.stock, req.type))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "message": "Товар успешно добавлен"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 7. Удалить товар
@app.post("/api/delete-product")
def delete_product(req: DeleteRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE user_id = %s", (req.admin_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=403, detail="Нет прав администратора")
        
        cursor.execute("DELETE FROM products WHERE id = %s", (req.product_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "message": "Товар удален"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 8. Редактировать товар (цена/кол-во)
@app.post("/api/edit-product")
def edit_product(req: EditRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE user_id = %s", (req.admin_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=403, detail="Нет прав администратора")
        
        cursor.execute("UPDATE products SET price = %s, stock = %s WHERE id = %s", (req.new_price, req.new_stock, req.product_id))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "message": "Товар обновлен"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ПРОВЕРКА ДЛЯ БОТА (при /start) ---
class CheckUserRequest(BaseModel):
    user_id: int

@app.post("/api/check-user")
def check_user(req: CheckUserRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE user_id = %s", (req.user_id,))
        is_admin = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return {"is_admin": is_admin}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
