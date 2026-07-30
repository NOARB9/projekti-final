# Vita Backend - Flask API
# E-commerce + Rush Hours + Game Rewards

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from database import get_db, init_db, hash_password, verify_password
from datetime import datetime, timedelta
import random

app = Flask(__name__)
CORS(app, supports_credentials=True)

@app.before_request
def before_request():
    g.db = get_db()

@app.teardown_request
def teardown_request(exception):
    db = g.pop('db', None)
    if db:
        db.close()

# ==================== AUTH ====================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()

    if not email or not password or not name:
        return jsonify({'error': 'All fields required'}), 400

    existing = g.db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    pw_hash = hash_password(password)
    g.db.execute(
        "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
        (email, pw_hash, name)
    )
    g.db.commit()

    user = g.db.execute("SELECT id, email, name, coins FROM users WHERE email = ?", (email,)).fetchone()
    return jsonify({'user': dict(user), 'token': str(user['id'])})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    user = g.db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid email or password'}), 401

    return jsonify({
        'user': {
            'id': user['id'],
            'email': user['email'],
            'name': user['name'],
            'coins': user['coins'],
            'address': user['address'],
            'phone': user['phone']
        },
        'token': str(user['id'])
    })

# ==================== PRODUCTS ====================

@app.route('/api/products', methods=['GET'])
def get_products():
    products = g.db.execute(
        "SELECT * FROM products WHERE is_active = 1 ORDER BY id"
    ).fetchall()

    # Get active rush hours
    rush = g.db.execute('''
        SELECT rh.*, rhp.product_id
        FROM rush_hours rh
        JOIN rush_hour_products rhp ON rh.id = rhp.rush_hour_id
        WHERE rh.is_active = 1
        AND rh.starts_at <= datetime('now')
        AND rh.ends_at > datetime('now')
    ''').fetchall()

    rush_map = {}
    active_rush = None
    for r in rush:
        if not active_rush:
            active_rush = {
                'id': r['id'],
                'name_sq': r['name_sq'],
                'name_en': r['name_en'],
                'discount': r['discount_percent'],
                'ends_at': r['ends_at']
            }
        rush_map[r['product_id']] = r['discount_percent']

    result = []
    for p in products:
        item = dict(p)
        discount = rush_map.get(p['id'], 0)
        item['discount_percent'] = discount
        item['sale_price'] = round(p['price'] * (1 - discount / 100), 2) if discount else p['price']
        result.append(item)

    return jsonify({
        'products': result,
        'rush_hour': active_rush
    })

# ==================== CART ====================

@app.route('/api/cart', methods=['GET'])
def get_cart():
    user_id = request.headers.get('Authorization', '')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    items = g.db.execute('''
        SELECT c.id as cart_id, c.quantity, p.*
        FROM cart_items c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (user_id,)).fetchall()

    total = 0
    result = []
    for item in items:
        d = dict(item)
        d['subtotal'] = round(item['price'] * item['quantity'], 2)
        total += d['subtotal']
        result.append(d)

    return jsonify({'items': result, 'total': round(total, 2), 'count': len(result)})

@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    user_id = request.headers.get('Authorization', '')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.json
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    existing = g.db.execute(
        "SELECT id, quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
        (user_id, product_id)
    ).fetchone()

    if existing:
        g.db.execute(
            "UPDATE cart_items SET quantity = ? WHERE id = ?",
            (existing['quantity'] + quantity, existing['id'])
        )
    else:
        g.db.execute(
            "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
            (user_id, product_id, quantity)
        )
    g.db.commit()

    return get_cart()

@app.route('/api/cart/remove/<int:product_id>', methods=['DELETE'])
def remove_from_cart(product_id):
    user_id = request.headers.get('Authorization', '')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    g.db.execute(
        "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
        (user_id, product_id)
    )
    g.db.commit()
    return get_cart()

# ==================== ORDERS ====================

@app.route('/api/orders', methods=['GET'])
def get_orders():
    user_id = request.headers.get('Authorization', '')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    orders = g.db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()

    result = []
    for o in orders:
        items = g.db.execute('''
            SELECT oi.*, p.name_sq, p.name_en, p.image
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (o['id'],)).fetchall()
        d = dict(o)
        d['items'] = [dict(i) for i in items]
        result.append(d)

    return jsonify({'orders': result})

@app.route('/api/orders/place', methods=['POST'])
def place_order():
    user_id = request.headers.get('Authorization', '')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    # Get cart items
    cart = g.db.execute('''
        SELECT c.*, p.price, p.stock
        FROM cart_items c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (user_id,)).fetchall()

    if not cart:
        return jsonify({'error': 'Cart is empty'}), 400

    # Check stock
    for item in cart:
        if item['stock'] < item['quantity']:
            return jsonify({'error': f'Not enough stock for product'}), 400

    # Check active rush hours for discounts
    rush = g.db.execute('''
        SELECT rhp.product_id, rh.discount_percent
        FROM rush_hours rh
        JOIN rush_hour_products rhp ON rh.id = rhp.rush_hour_id
        WHERE rh.is_active = 1 AND rh.starts_at <= datetime('now') AND rh.ends_at > datetime('now')
    ''').fetchall()
    rush_discounts = {r['product_id']: r['discount_percent'] for r in rush}

    # Calculate total
    total = 0
    discount_total = 0
    for item in cart:
        base = item['price'] * item['quantity']
        discount = rush_discounts.get(item['product_id'], 0)
        discount_amount = round(base * discount / 100, 2)
        total += base - discount_amount
        discount_total += discount_amount

    # Create order
    g.db.execute(
        "INSERT INTO orders (user_id, total, discount_applied, status) VALUES (?, ?, ?, 'confirmed')",
        (user_id, total, discount_total)
    )
    order_id = g.db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Create order items
    for item in cart:
        base = item['price']
        discount = rush_discounts.get(item['product_id'], 0)
        final_price = round(base * (1 - discount / 100), 2)
        g.db.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
            (order_id, item['product_id'], item['quantity'], final_price)
        )
        # Reduce stock
        g.db.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (item['quantity'], item['product_id'])
        )

    # Clear cart
    g.db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))

    # Award coins: 10 per € spent
    coins_earned = int(total * 10)
    g.db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (coins_earned, user_id))

    g.db.commit()

    return jsonify({
        'order_id': order_id,
        'total': round(total, 2),
        'discount': round(discount_total, 2),
        'coins_earned': coins_earned
    })

# ==================== RUSH HOURS ====================

@app.route('/api/rush-hours', methods=['GET'])
def get_rush_hours():
    now = datetime.now().isoformat()

    active = g.db.execute('''
        SELECT rh.*, rhp.product_id
        FROM rush_hours rh
        JOIN rush_hour_products rhp ON rh.id = rhp.rush_hour_id
        WHERE rh.is_active = 1 AND rh.starts_at <= ? AND rh.ends_at > ?
    ''', (now, now)).fetchall()

    if not active:
        return jsonify({'active': None, 'products': []})

    rush = active[0]
    product_ids = [r['product_id'] for r in active]
    products = g.db.execute(
        f"SELECT * FROM products WHERE id IN ({','.join('?'*len(product_ids))})",
        product_ids
    ).fetchall()

    for p in products:
        p = dict(p)
        p['discount_percent'] = rush['discount_percent']
        p['sale_price'] = round(p['price'] * (1 - rush['discount_percent'] / 100), 2)

    return jsonify({
        'active': {
            'id': rush['id'],
            'name_sq': rush['name_sq'],
            'name_en': rush['name_en'],
            'discount': rush['discount_percent'],
            'ends_at': rush['ends_at'],
            'seconds_left': max(0, int((datetime.fromisoformat(rush['ends_at']) - datetime.now()).total_seconds()))
        },
        'products': [dict(p) for p in products]
    })

# ==================== GAME REWARDS ====================

@app.route('/api/game/result', methods=['POST'])
def submit_game_result():
    user_id = request.headers.get('Authorization', '')
    data = request.json

    tests_run = data.get('tests_run', 0)
    tests_ok = data.get('tests_ok', 0)
    tests_bad = data.get('tests_bad', 0)
    product = data.get('product', '')
    decision = data.get('decision', '')
    was_correct = data.get('was_correct', False)

    # Calculate coins: base 5 + bonus for correct decision
    coins = 5 + (tests_ok * 2)
    if was_correct:
        coins += 15  # bonus for correct decision

    if user_id:
        g.db.execute('''
            INSERT INTO game_sessions (user_id, product_tested, tests_run, tests_ok, tests_bad, decision, was_correct, coins_earned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, product, tests_run, tests_ok, tests_bad, decision, 1 if was_correct else 0, coins))
        g.db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (coins, user_id))
        g.db.commit()

        # Check for achievements
        total_games = g.db.execute(
            "SELECT COUNT(*) as c FROM game_sessions WHERE user_id = ?", (user_id,)
        ).fetchone()['c']

        achievements = []
        if total_games == 1:
            achievements.append({'type': 'first_game', 'name_sq': 'Testuesi i Parë', 'name_en': 'First Tester'})
        if total_games == 5:
            achievements.append({'type': 'five_games', 'name_sq': 'Laborant i Zellshëm', 'name_en': 'Diligent Lab Tech'})
        if total_games == 10:
            achievements.append({'type': 'ten_games', 'name_sq': 'Master i Laboratorit', 'name_en': 'Lab Master'})

        user = g.db.execute("SELECT coins FROM users WHERE id = ?", (user_id,)).fetchone()

        return jsonify({
            'coins_earned': coins,
            'total_coins': user['coins'],
            'achievements': achievements
        })

    return jsonify({'coins_earned': coins, 'total_coins': 0, 'achievements': []})

@app.route('/api/game/leaderboard', methods=['GET'])
def game_leaderboard():
    leaders = g.db.execute('''
        SELECT u.name, SUM(gs.coins_earned) as total_coins, COUNT(*) as games_played
        FROM game_sessions gs
        JOIN users u ON gs.user_id = u.id
        GROUP BY gs.user_id
        ORDER BY total_coins DESC
        LIMIT 10
    ''').fetchall()

    return jsonify({'leaderboard': [dict(l) for l in leaders]})

@app.route('/api/user/rewards', methods=['GET'])
def user_rewards():
    user_id = request.headers.get('Authorization', '')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    rewards = g.db.execute(
        "SELECT * FROM game_rewards WHERE user_id = ? ORDER BY earned_at DESC",
        (user_id,)
    ).fetchall()

    games = g.db.execute(
        "SELECT * FROM game_sessions WHERE user_id = ? ORDER BY played_at DESC LIMIT 20",
        (user_id,)
    ).fetchall()

    user = g.db.execute("SELECT coins FROM users WHERE id = ?", (user_id,)).fetchone()

    return jsonify({
        'coins': user['coins'],
        'rewards': [dict(r) for r in rewards],
        'recent_games': [dict(g) for g in games]
    })

# ==================== USER PROFILE ====================

@app.route('/api/user/profile', methods=['GET'])
def get_profile():
    user_id = request.headers.get('Authorization', '')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    user = g.db.execute(
        "SELECT id, email, name, address, phone, coins, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    order_count = g.db.execute(
        "SELECT COUNT(*) as c FROM orders WHERE user_id = ?", (user_id,)
    ).fetchone()['c']

    game_count = g.db.execute(
        "SELECT COUNT(*) as c FROM game_sessions WHERE user_id = ?", (user_id,)
    ).fetchone()['c']

    return jsonify({
        'user': dict(user),
        'stats': {
            'orders': order_count,
            'games_played': game_count
        }
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5050)
