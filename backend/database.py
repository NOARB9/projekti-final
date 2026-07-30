# Vita Backend - Database Schema
# SQLite database for Vita dairy e-commerce platform

import sqlite3
import os
from datetime import datetime, timedelta
import hashlib
import secrets

DB_PATH = os.path.join(os.path.dirname(__file__), 'vita.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${h}"

def verify_password(password, stored):
    salt, h = stored.split('$', 1)
    return hashlib.sha256((password + salt).encode()).hexdigest() == h

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            address TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            coins INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name_sq TEXT NOT NULL,
            name_en TEXT NOT NULL,
            description_sq TEXT DEFAULT '',
            description_en TEXT DEFAULT '',
            price REAL NOT NULL,
            image TEXT DEFAULT '',
            category TEXT DEFAULT '',
            fat_percent TEXT DEFAULT '',
            stock INTEGER DEFAULT 100,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            discount_applied REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Order items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Rush Hours (flash sales) table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rush_hours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_sq TEXT NOT NULL,
            name_en TEXT NOT NULL,
            discount_percent INTEGER NOT NULL,
            starts_at TIMESTAMP NOT NULL,
            ends_at TIMESTAMP NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Rush Hour products (which products are on sale)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rush_hour_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rush_hour_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            FOREIGN KEY (rush_hour_id) REFERENCES rush_hours(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Game rewards table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reward_type TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            description TEXT DEFAULT '',
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Game sessions (track milk testing lab results)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_tested TEXT DEFAULT '',
            tests_run INTEGER DEFAULT 0,
            tests_ok INTEGER DEFAULT 0,
            tests_bad INTEGER DEFAULT 0,
            decision TEXT DEFAULT '',
            was_correct INTEGER DEFAULT 0,
            coins_earned INTEGER DEFAULT 0,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Cart (temporary, per-user)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Seed products if empty
    seed_products(cursor)

    # Seed an active rush hour if none exist
    seed_rush_hour(cursor)

    conn.commit()
    conn.close()

def seed_products(cursor):
    cursor.execute("SELECT COUNT(*) as c FROM products")
    if cursor.fetchone()['c'] > 0:
        return

    products = [
        ('milk', 'Qumësht i Freskët', 'Fresh Milk', 'Qumësht i pasterizuar i plotë', 'Full-fat pasteurized milk', 1.50, 'qumeshti-vita.png', 'qumesht', '3.2%'),
        ('kos', 'Kos', 'Kos (Yogurt)', 'Kos tradicional shqiptar', 'Traditional Albanian yogurt', 1.20, 'jogurt-vita.png', 'kos', '3.5%'),
        ('jogurt', 'Jogurt', 'Yogurt', 'Jogurt i lehtë dhe freskues', 'Light and refreshing yogurt', 0.90, 'jogurt-vita.png', 'jogurt', '2.0%'),
        ('cheese', 'Djathë i Bardhë', 'White Cheese', 'Djathë tradicional shqiptar', 'Traditional Albanian white cheese', 3.50, 'djath-vita.png', 'djath', '18%'),
        ('ayran', 'Ayran', 'Ayran', 'Pije tradicionale freskuese', 'Traditional refreshing drink', 0.80, 'ayran-vita.png', 'ayran', '1.5%'),
        ('cooking-cream', 'Krem Gatimi', 'Cooking Cream', 'Krem i lëngshëm për gatim', 'Liquid cream for cooking', 2.00, 'cooking-cream-vita.png', 'krem', '15%'),
        ('whipping-cream', 'Krem Pana', 'Whipping Cream', 'Krem i trashë për ëmbëlsira', 'Thick cream for desserts', 2.50, 'whipping-cream-vita.png', 'krem', '35%'),
        ('tamel', 'Tamel', 'Tamel', 'Produkt i fermentuar tradicional', 'Traditional fermented product', 1.10, 'tamel-vita.png', 'tamel', '2.5%'),
    ]

    for p in products:
        cursor.execute('''
            INSERT INTO products (slug, name_sq, name_en, description_sq, description_en, price, image, category, fat_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', p)

def seed_rush_hour(cursor):
    cursor.execute("SELECT COUNT(*) as c FROM rush_hours WHERE ends_at > datetime('now')")
    if cursor.fetchone()['c'] > 0:
        return

    # Create an active rush hour for the next hour
    now = datetime.now()
    end = now + timedelta(hours=1)

    cursor.execute('''
        INSERT INTO rush_hours (name_sq, name_en, discount_percent, starts_at, ends_at)
        VALUES (?, ?, ?, ?, ?)
    ''', ('Vita Flash', 'Vita Flash', 30, now.isoformat(), end.isoformat()))

    rush_id = cursor.lastrowid

    # Add random products to the rush hour
    cursor.execute("SELECT id FROM products ORDER BY RANDOM() LIMIT 3")
    for row in cursor.fetchall():
        cursor.execute('''
            INSERT INTO rush_hour_products (rush_hour_id, product_id)
            VALUES (?, ?)
        ''', (rush_id, row['id']))

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
