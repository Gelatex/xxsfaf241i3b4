from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta
import uuid
import json
import math
import random

app = Flask(__name__)
CORS(app)

DATABASE = 'falunrykten.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Posts table
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id TEXT PRIMARY KEY,
                  title TEXT,
                  author TEXT,
                  anonymous INTEGER,
                  content TEXT,
                  date TEXT,
                  likes INTEGER,
                  liked_by TEXT,
                  vip INTEGER,
                  images TEXT,
                  comments TEXT,
                  effect TEXT)''')
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY,
                  level INTEGER DEFAULT 1,
                  xp INTEGER DEFAULT 0,
                  coins INTEGER DEFAULT 50,
                  total_posts INTEGER DEFAULT 0,
                  total_likes_received INTEGER DEFAULT 0,
                  total_comments_given INTEGER DEFAULT 0,
                  login_streak INTEGER DEFAULT 0,
                  last_login TEXT,
                  last_post_time TEXT)''')
    # Transactions for effects
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id TEXT PRIMARY KEY,
                  username TEXT,
                  effect_name TEXT,
                  coins_spent INTEGER,
                  expires_at TEXT)''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

init_db()

# ---------- HJÄLPFUNKTIONER ----------
def get_user(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def create_user_if_not_exists(username):
    if get_user(username):
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO users (username, coins, last_login) VALUES (?, ?, ?)", (username, 50, None))
    conn.commit()
    conn.close()

def update_user(username, **kwargs):
    conn = get_db()
    c = conn.cursor()
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [username]
    c.execute(f"UPDATE users SET {set_clause} WHERE username = ?", values)
    conn.commit()
    conn.close()

def add_xp(username, amount):
    user = get_user(username)
    if not user:
        create_user_if_not_exists(username)
        user = get_user(username)
    new_xp = user['xp'] + amount
    old_level = user['level']
    # Level-up formel: 100 XP per level
    new_level = 1 + new_xp // 100
    if new_level > old_level:
        bonus_coins = new_level * 50
        new_coins = user['coins'] + bonus_coins
        update_user(username, xp=new_xp, level=new_level, coins=new_coins)
        return True, new_level, bonus_coins
    else:
        update_user(username, xp=new_xp)
        return False, old_level, 0

def add_coins(username, amount):
    user = get_user(username)
    if user:
        update_user(username, coins=user['coins'] + amount)
    else:
        create_user_if_not_exists(username)
        update_user(username, coins=50 + amount)

def can_post(username):
    user = get_user(username)
    if not user:
        return True, 0
    last_post = user.get('last_post_time')
    if not last_post:
        return True, 0
    # Cooldown baserat på level
    level = user['level']
    if level >= 10:
        cooldown_min = 1
    elif level >= 6:
        cooldown_min = 3
    elif level >= 3:
        cooldown_min = 5
    else:
        cooldown_min = 10
    last = datetime.fromisoformat(last_post)
    if datetime.now() - last < timedelta(minutes=cooldown_min):
        remaining = int((last + timedelta(minutes=cooldown_min) - datetime.now()).total_seconds())
        return False, remaining
    return True, 0

def get_active_effects(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT effect_name, expires_at FROM transactions WHERE username = ? AND expires_at > ?", 
              (username, datetime.now().isoformat()))
    rows = c.fetchall()
    conn.close()
    return [row['effect_name'] for row in rows]

# ---------- API ROUTES ----------
@app.route('/')
def home():
    return "🔥 Falunrykten API – Gamification Edition"

@app.route('/posts', methods=['GET'])
def get_posts():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM posts")
    rows = c.fetchall()
    posts = []
    for row in rows:
        post = dict(row)
        post['anonymous'] = bool(post['anonymous'])
        post['vip'] = bool(post['vip'])
        post['liked_by'] = json.loads(post['liked_by']) if post['liked_by'] else []
        post['images'] = json.loads(post['images']) if post['images'] else []
        post['comments'] = json.loads(post['comments']) if post['comments'] else []
        posts.append(post)
    conn.close()
    # VIP först, sedan datum fallande
    posts.sort(key=lambda x: (0 if x['vip'] else 1, x['date']), reverse=False)
    return jsonify(posts)

@app.route('/posts', methods=['POST'])
def add_post():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("content"):
        return jsonify({"error": "Titel och innehåll krävs"}), 400
    
    username = data.get("username")
    if not username:
        return jsonify({"error": "Du måste vara inloggad"}), 401
    
    create_user_if_not_exists(username)
    
    # Cooldown check
    ok, remaining = can_post(username)
    if not ok:
        return jsonify({"error": f"Cooldown: vänta {remaining} sekunder"}), 429
    
    is_anonymous = data.get("anonymous", False)
    is_vip = data.get("vip", False) and username == "Ebbe"
    images = data.get("images", [])
    effect = data.get("effect")
    if effect and effect not in get_active_effects(username):
        effect = None  # Användaren har inte den effekten aktiv
    
    post_id = uuid.uuid4().hex
    new_post = {
        "id": post_id,
        "title": data["title"],
        "author": "Anonym" if is_anonymous else username,
        "anonymous": is_anonymous,
        "content": data["content"],
        "date": datetime.now().isoformat(),
        "likes": 0,
        "liked_by": [],
        "vip": is_vip,
        "images": images,
        "comments": [],
        "effect": effect
    }
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO posts 
                 (id, title, author, anonymous, content, date, likes, liked_by, vip, images, comments, effect)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (post_id, new_post['title'], new_post['author'], int(new_post['anonymous']),
               new_post['content'], new_post['date'], new_post['likes'],
               json.dumps(new_post['liked_by']), int(new_post['vip']),
               json.dumps(new_post['images']), json.dumps(new_post['comments']), effect))
    conn.commit()
    # Uppdatera användarens last_post_time och total_posts
    user = get_user(username)
    update_user(username, 
                last_post_time=datetime.now().isoformat(),
                total_posts=user['total_posts'] + 1)
    add_xp(username, 20)
    add_coins(username, 10)
    conn.close()
    return jsonify({"message": "Ryktet publicerat!", "id": post_id})

@app.route('/posts/<post_id>/like', methods=['POST'])
def like_post(post_id):
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Ange användarnamn"}), 400
    
    create_user_if_not_exists(username)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT author, likes, liked_by FROM posts WHERE id = ?", (post_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Inlägg finns inte"}), 404
    
    liked_by = json.loads(row[2]) if row[2] else []
    if username in liked_by:
        conn.close()
        return jsonify({"message": "Redan gillat"}), 200
    
    new_likes = row[1] + 1
    liked_by.append(username)
    c.execute("UPDATE posts SET likes = ?, liked_by = ? WHERE id = ?",
              (new_likes, json.dumps(liked_by), post_id))
    conn.commit()
    # Ge XP och coins till författaren (om inte anonym)
    author = row[0]
    if author != "Anonym":
        add_xp(author, 2)
        add_coins(author, 1)
        # Uppdatera total_likes_received för författaren
        author_user = get_user(author)
        if author_user:
            update_user(author, total_likes_received=author_user['total_likes_received'] + 1)
    # Ge XP till den som gillar
    add_xp(username, 1)
    add_coins(username, 1)
    conn.close()
    return jsonify({"likes": new_likes})

@app.route('/posts/<post_id>/comment', methods=['POST'])
def add_comment(post_id):
    data = request.get_json()
    username = data.get("username")
    text = data.get("text")
    if not username or not text:
        return jsonify({"error": "Användarnamn och kommentar krävs"}), 400
    
    create_user_if_not_exists(username)
    
    comment = {
        "username": username,
        "text": text,
        "date": datetime.now().isoformat()
    }
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT author, comments FROM posts WHERE id = ?", (post_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Inlägg finns inte"}), 404
    
    comments = json.loads(row[1]) if row[1] else []
    comments.append(comment)
    c.execute("UPDATE posts SET comments = ? WHERE id = ?", (json.dumps(comments), post_id))
    conn.commit()
    # Belöning till författaren (om inte anonym)
    author = row[0]
    if author != "Anonym":
        add_coins(author, 2)
    # Belöning till kommenteraren
    add_xp(username, 1)
    add_coins(username, 1)
    # Uppdatera total_comments_given
    user = get_user(username)
    if user:
        update_user(username, total_comments_given=user['total_comments_given'] + 1)
    conn.close()
    return jsonify({"message": "Kommentar tillagd"})

@app.route('/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    username = request.headers.get("X-User")
    if username != "Ebbe":
        return jsonify({"error": "Endast admin (Ebbe) kan radera"}), 403
    
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    if c.rowcount == 0:
        conn.close()
        return jsonify({"error": "Inlägg ej funnet"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Ryktet raderat"})

@app.route('/user/<username>', methods=['GET'])
def get_user_info(username):
    user = get_user(username)
    if not user:
        create_user_if_not_exists(username)
        user = get_user(username)
    active_effects = get_active_effects(username)
    user_data = dict(user)
    user_data['active_effects'] = active_effects
    # Beräkna XP till nästa level
    current_level = user_data['level']
    xp_for_current_level = (current_level - 1) * 100
    xp_in_level = user_data['xp'] - xp_for_current_level
    xp_needed = 100 - xp_in_level
    user_data['xp_needed'] = max(0, xp_needed)
    return jsonify(user_data)

@app.route('/user/<username>/daily', methods=['POST'])
def daily_reward(username):
    user = get_user(username)
    if not user:
        create_user_if_not_exists(username)
        user = get_user(username)
    today = datetime.now().date().isoformat()
    if user['last_login'] == today:
        return jsonify({"error": "Redan fått daglig belöning idag"}), 400
    # Beräkna streak
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    if user['last_login'] == yesterday:
        streak = user['login_streak'] + 1
    else:
        streak = 1
    bonus = 5 + (streak - 1)  # 5,6,7...
    new_coins = user['coins'] + bonus
    update_user(username, last_login=today, login_streak=streak, coins=new_coins)
    return jsonify({"coins": new_coins, "streak": streak})

@app.route('/shop/buy', methods=['POST'])
def buy_effect():
    data = request.get_json()
    username = data.get("username")
    effect = data.get("effect")
    if not username or not effect:
        return jsonify({"error": "Saknas data"}), 400
    
    prices = {
        "🔥 Fire Glow": 100,
        "💎 Diamond Glow": 250,
        "👑 Royal Crown": 500,
        "✨ Sparkle": 150,
        "🌈 Rainbow Border": 300,
        "💀 Mystery Box": 75
    }
    if effect not in prices:
        return jsonify({"error": "Ogiltig effekt"}), 400
    
    user = get_user(username)
    if not user:
        create_user_if_not_exists(username)
        user = get_user(username)
    
    if user['coins'] < prices[effect]:
        return jsonify({"error": "Inte tillräckligt med coins"}), 400
    
    # Mystery box: slumpmässig varaktighet (1-7 dagar)
    if effect == "💀 Mystery Box":
        days = random.randint(1, 7)
        expires = (datetime.now() + timedelta(days=days)).isoformat()
    else:
        expires = (datetime.now() + timedelta(days=7)).isoformat()
    
    conn = get_db()
    c = conn.cursor()
    tid = uuid.uuid4().hex
    c.execute("INSERT INTO transactions (id, username, effect_name, coins_spent, expires_at) VALUES (?,?,?,?,?)",
              (tid, username, effect, prices[effect], expires))
    new_coins = user['coins'] - prices[effect]
    c.execute("UPDATE users SET coins = ? WHERE username = ?", (new_coins, username))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Effekt '{effect}' köpt!", "coins": new_coins, "expires": expires})

@app.route('/user/<username>/effects', methods=['GET'])
def get_user_effects(username):
    effects = get_active_effects(username)
    return jsonify(effects)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
