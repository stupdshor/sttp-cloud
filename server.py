from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import io
import csv
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

def get_db_connection():
    url = DATABASE_URL.replace("postgres://", "postgresql://")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, brand TEXT,
            price REAL, stock INTEGER, type TEXT
        )
    ''')
    cursor.execute('CREATE TABLE IF NOT EXISTS admins (user_id BIGINT PRIMARY KEY)')
    cursor.execute('CREATE TABLE IF NOT EXISTS disabled_stations (station_name TEXT PRIMARY KEY)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT INTO settings (key, value) VALUES ('banner_title', 'STTP SHOP') ON CONFLICT DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('banner_subtitle', 'Ждем ваших заказов 🔥') ON CONFLICT DO NOTHING")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            customer_name TEXT,
            address TEXT,
            total_price REAL,
            status TEXT DEFAULT 'Новый',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            items_json TEXT
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

try: init_db()
except Exception as e: print(f"Ошибка инициализации БД: {e}")

# --- МОДЕЛИ ---
class OrderItem(BaseModel):
    product_id: int
    quantity: int

class Order(BaseModel):
    items: List[OrderItem]
    name: str
    phone: str
    address: str

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

class ImportProduct(BaseModel):
    title: str
    brand: str
    price: float
    stock: int
    type: str

class ContentRequest(BaseModel):
    banner_title: str
    banner_subtitle: str

class OrderStatusRequest(BaseModel):
    order_id: int
    new_status: str

# --- ЭКСПОРТ ФАЙЛОВ ---
@app.get("/api/download/export")
def export_csv():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, brand, price, stock, type FROM products ORDER BY type, brand, title")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Название', 'Бренд', 'Цена', 'Количество', 'Категория'])
    for row in rows:
        writer.writerow([row['title'], row['brand'], row['price'], row['stock'], row['type']])
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=sttp_export.csv"
    return response

@app.get("/api/download/template")
def download_template():
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Название', 'Бренд', 'Цена', 'Количество', 'Категория'])
    writer.writerow(['Пример вкуса', 'Пример бренда', '10.5', '100', 'Жидкость'])
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=sttp_template.csv"
    return response

# --- ОСНОВНЫЕ API ---
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
    items_info = []
    total_price = 0
    for item in order.items:
        cursor.execute("SELECT id, title, price, stock FROM products WHERE id = %s", (item.product_id,))
        row = cursor.fetchone()
        if not row or row['stock'] < item.quantity:
            conn.close()
            raise HTTPException(status_code=400, detail="Недостаточно товара")
        
        total_price += row['price'] * item.quantity
        
        # Сохраняем ID товара для точного возврата
        items_info.append({
            "id": row['id'], 
            "title": row['title'], 
            "qty": item.quantity, 
            "price": row['price']
        })
        
        cursor.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (item.quantity, item.product_id))
        
    items_json = json.dumps(items_info, ensure_ascii=False)
    cursor.execute("INSERT INTO orders (customer_name, address, total_price, items_json) VALUES (%s, %s, %s, %s)", (order.name, order.address, total_price, items_json))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.get("/api/orders")
def get_orders():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

@app.post("/api/update-order-status")
def update_order_status(req: OrderStatusRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, items_json FROM orders WHERE id = %s", (req.order_id,))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Заказ не найден")
        
    current_status = order['status']
    items = json.loads(order['items_json'])
    
    # Если статус меняется НА "Отменен" - возвращаем товары по ID
    if req.new_status == "Отменен" and current_status != "Отменен":
        for item in items:
            if "id" in item:
                cursor.execute("UPDATE products SET stock = stock + %s WHERE id = %s", (item['qty'], item['id']))
            else:
                cursor.execute("UPDATE products SET stock = stock + %s WHERE title = %s", (item['qty'], item['title']))
            
    # Если статус меняется С "Отменен" на любой другой - снова списываем товары по ID
    elif req.new_status != "Отменен" and current_status == "Отменен":
        for item in items:
            if "id" in item:
                cursor.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (item['qty'], item['id']))
            else:
                cursor.execute("UPDATE products SET stock = stock - %s WHERE title = %s", (item['qty'], item['title']))

    cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (req.new_status, req.order_id))
    
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

# --- АДМИНСКИЕ API (БЕЗ ПРОВЕРКИ ПОДПИСИ) ---
@app.post("/api/add-product")
def add_product_admin(req: ProductRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES (%s, %s, %s, %s, %s)", 
                   (req.title, req.brand, req.price, req.stock, req.type))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.post("/api/import-products")
def import_products(products: List[ImportProduct]):
    conn = get_db_connection()
    cursor = conn.cursor()
    count = 0
    for p in products:
        cursor.execute("SELECT id FROM products WHERE title = %s AND brand = %s", (p.title, p.brand))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("UPDATE products SET price = %s, stock = stock + %s WHERE id = %s", (p.price, p.stock, existing['id']))
        else:
            cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES (%s, %s, %s, %s, %s)", (p.title, p.brand, p.price, p.stock, p.type))
        count += 1
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok", "imported": count}

@app.post("/api/delete-product")
def delete_product(req: DeleteRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = %s", (req.product_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.post("/api/edit-product")
def edit_product(req: EditRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET price = %s, stock = %s WHERE id = %s", (req.new_price, req.new_stock, req.product_id))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.post("/api/seed-brands")
def seed_brands():
    start_brands = ["Annima Love", "Bjorn", "Catswill", "Duall", "Elfliq", "Hotspot", "Isterika", "Monster", "OGGO prime", "Podonki", "Rick and Morty", "SKL", "Анархия V2", "Злая монашка", "Призрак 69", "Самоубийца"]
    conn = get_db_connection()
    cursor = conn.cursor()
    added_count = 0
    for brand in start_brands:
        cursor.execute("SELECT id FROM products WHERE brand = %s LIMIT 1", (brand,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO products (title, brand, price, stock, type) VALUES ('Новый вкус', %s, 0.0, 0, 'Жидкость')", (brand,))
            added_count += 1
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok", "added": added_count}

@app.post("/api/toggle-station")
def toggle_station(req: ToggleStationRequest):
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

@app.get("/api/stations")
def get_stations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT station_name FROM disabled_stations")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [row['station_name'] for row in rows]

@app.post("/api/content")
def update_content(req: ContentRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = %s WHERE key = 'banner_title'", (req.banner_title,))
    cursor.execute("UPDATE settings SET value = %s WHERE key = 'banner_subtitle'", (req.banner_subtitle,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.get("/api/content")
def get_content():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('banner_title', 'banner_subtitle')")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    res = {row['key']: row['value'] for row in rows}
    return {"banner_title": res.get('banner_title', 'STTP SHOP'), "banner_subtitle": res.get('banner_subtitle', 'Ждем ваших заказов 🔥')}

# --- ДЛЯ БОТА ---
@app.get("/api/check-admin")
def check_admin():
    return {"is_admin": True} # Заглушка, так как проверка подписи убрана

@app.get("/api/get-admins")
def get_admins():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [row['user_id'] for row in rows]

@app.post("/api/add-admin")
def add_admin(req: dict):
    if req.get("owner_id") != 1340303313: raise HTTPException(status_code=403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (req["user_id"],))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok"}

@app.post("/api/remove-admin")
def remove_admin(req: dict):
    if req.get("owner_id") != 1340303313: raise HTTPException(status_code=403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = %s", (req["user_id"],))
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
