from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional
import os
import uvicorn
import hashlib
import hmac
import json
from urllib.parse import parse_qsl
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

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")

def validate_telegram_data(init_data: str) -> Optional[dict]:
    try:
        parsed_data = dict(parse_qsl(init_data))
        if "hash" not in parsed_data:
            return None
        
        hash_from_telegram = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash == hash_from_telegram:
            if "user" in parsed_data:
                return json.loads(parsed_data["user"])
        return None
    except Exception as e:
        print(f"Ошибка валидации: {e}")
        return None

def get_db_connection():
    url = DATABASE_URL.replace("postgres://", "postgresql://")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Товары
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
    
    # Админы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (user_id BIGINT PRIMARY KEY)
    ''')
    
    # Выключенные станции (новая таблица)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disabled_stations (
            station_name TEXT PRIMARY KEY
        )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()['count'] == 0:
        cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES (%s, %s, %s, %s, %s)", 
                       ('Персиковый йогурт', 'Annima', 22.0, 10, 'Жидкость'))
    conn.commit()
    cursor.close()
    conn.close()

try:
    init_db()
    print("База данных успешно инициализирована!")
except Exception as e:
    print(f"Ошибка инициализации БД: {e}")

class OrderItem(BaseModel):
    product_id: int
    quantity: int

class Order(BaseModel):
    items: List[OrderItem]
    name: str
    phone: str

class ProductRequest(BaseModel):
    title: str
    brand: str
    price: float
    stock: int
    type: str

class DeleteRequest(BaseModel):
    product_id: int

class EditRequest(BaseModel):
    product_id: int
    new_price: float
    new_stock: int

class ToggleStationRequest(BaseModel):
    station_name: str
    is_disabled: bool

@app.get("/api/products")
def get_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

@app.post("/api/order")
def create_order(order: Order):
    conn = get_db_connection()
    cursor = conn.cursor()
    for item in order.items:
        cursor.execute("SELECT stock FROM products WHERE id = %s", (item.product_id,))
        row = cursor.fetchone()
        if not row or row['stock'] < item.quantity:
            conn.close()
            raise HTTPException(status_code=400, detail="Недостаточно товара")
        cursor.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (item.quantity, item.product_id))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

def check_admin_rights(init_data: str):
    user_data = validate_telegram_data(init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Неверная подпись Telegram")
    
    user_id = user_data.get("id")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE user_id = %s", (user_id,))
    is_admin = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    
    if not is_admin:
        raise HTTPException(status_code=403, detail="Вы не администратор")
    return user_id

@app.post("/api/add-product")
def add_product_admin(req: ProductRequest, x_init_data: str = Header(None)):
    check_admin_rights(x_init_data)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES (%s, %s, %s, %s, %s)", 
                   (req.title, req.brand, req.price, req.stock, req.type))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.post("/api/delete-product")
def delete_product(req: DeleteRequest, x_init_data: str = Header(None)):
    check_admin_rights(x_init_data)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = %s", (req.product_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.post("/api/edit-product")
def edit_product(req: EditRequest, x_init_data: str = Header(None)):
    check_admin_rights(x_init_data)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET price = %s, stock = %s WHERE id = %s", (req.new_price, req.new_stock, req.product_id))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.get("/api/check-admin")
def check_admin(x_init_data: str = Header(None)):
    try:
        user_id = check_admin_rights(x_init_data)
        return {"is_admin": True, "user_id": user_id}
    except:
        return {"is_admin": False}

@app.get("/api/stations")
def get_stations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT station_name FROM disabled_stations")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [row['station_name'] for row in rows]

@app.post("/api/toggle-station")
def toggle_station(req: ToggleStationRequest, x_init_data: str = Header(None)):
    check_admin_rights(x_init_data)
    conn = get_db_connection()
    cursor = conn.cursor()
    if req.is_disabled:
        cursor.execute("INSERT INTO disabled_stations (station_name) VALUES (%s) ON CONFLICT DO NOTHING", (req.station_name,))
    else:
        cursor.execute("DELETE FROM disabled_stations WHERE station_name = %s", (req.station_name,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.post("/api/add-admin")
def add_admin(req: dict):
    if req.get("owner_id") != 1340303313:
        raise HTTPException(status_code=403, detail="Нет прав")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (req["user_id"],))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.post("/api/check-user")
def check_user(req: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE user_id = %s", (req["user_id"],))
    is_admin = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return {"is_admin": is_admin}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
