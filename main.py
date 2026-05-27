from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime, timedelta
import uuid
import math

app = Flask(__name__)
CORS(app)

DATABASE = 'falunrykten.db'

# ---------- HJÄLPFUNKTIONER ----------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Posts-tabell (med stöd för effekt)
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
    # Users-tabell
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY,
                  level INTEGER DEFAULT 1,
                  xp INTEGER DEFAULT 0,
                  coins INTEGER DEFAULT 50,
                  total_posts INTEGER DEFAULT 0,
                  total_likes_received INTEGER DEFAULT 0,
                  total_comments INTEGER DEFAULT 0,
                  login_streak INTEGER DEFAULT 0,
                  last_login_date TEXT,
                  last_post_time TEXT,
                  active_effects TEXT DEFAULT '[]')''')  # lista med köpta effekter (namn, köptid, varaktighet)
    # Butikstransaktioner
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id TEXT PRIMARY KEY,
                  username TEXT,
                  effect_name TEXT,
                  coins_spent INTEGER,
                  purchase_date TEXT,
                  expires_at TEXT)''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# XP- och levelberäkning
def calculate_level(xp):
    # level = floor(sqrt(xp / 100)) + 1, max level 10
    level = int(math.sqrt(xp / 100)) + 1
    return min(level, 10)

def xp_for_next_level(current_xp):
    level = calculate_level(current_xp)
    if level >= 10:
        return None
    next_level_xp = ((level) ** 2) * 100
    return next_level_xp

def add_xp(username, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT xp FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if row:
        new_xp = row['xp'] + amount
        new_level = calculate_level(new_xp)
        c.execute("UPDATE users SET xp = ? WHERE username = ?", (new_xp, username))
        conn.commit()
        # Kolla level-up
        c.execute("SELECT level FROM users WHERE username = ?", (username,))
        old_level = c.fetchone()['level']
        if new_level > old_level:
            # Level-up bonus: coins + 50
            c.execute("UPDATE users SET coins = coins + 50 WHERE username = ?", (username,))
            conn.commit()
    conn.close()

def add_coins(username, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()

def remove_coins(username, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins - ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()

def can_post(username):
    """Kontrollera cooldown baserat på level"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT level, last_post_time FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return True  # ny användare får posta
    level = row['level']
    last_post = row['last_post_time']
    if not last_post:
        conn.close()
        return True
    last_post_dt = datetime.fromisoformat(last_post)
    cooldown_minutes = {1:10, 2:10, 3:5, 4:5, 5:3, 6:3, 7:2, 8:2, 9:1, 10:1}
    wait = cooldown_minutes.get(level, 10)
    diff = datetime.now() - last_post_dt
    allowed = diff.total_seconds() >= wait * 60
    conn.close()
    return allowed

def update_last_post_time(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET last_post_time = ? WHERE username = ?", (datetime.now().isoformat(), username))
    conn.commit()
    conn.close()

# ---------- ENDPOINTS ----------
@app.route('/')
def home():
    return "🔥 Falunrykten API – full gamification online"

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
        post['effect'] = post['effect'] or ''
        posts.append(post)
    conn.close()
    # Sortera: VIP först, sedan datum nyast
    posts.sort(key=lambda x: (0 if x['vip'] else 1, x['date']), reverse=False)
    return jsonify(posts)

@app.route('/posts', methods=['POST'])
def add_post():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("content"):
        return jsonify({"error": "Titel och innehåll krävs"}), 400
    
    username = data.get("username")
    if not username:
        return jsonify({"error": "Inte inloggad"}), 401
    
    # Cooldown-koll
    if not can_post(username):
        return jsonify({"error": "Cooldown aktiv, vänta lite."}), 429
    
    is_anonymous = data.get("anonymous", False)
    is_vip = data.get("vip", False) and username == "Ebbe"
    images = data.get("images", [])
    effect = data.get("effect", "")  # effektnamn som användaren valt
    
    # Kolla om användaren äger effekten och har tillräckligt med coins? Nej, effekten köps separat och appliceras gratis.
    # Vid köp av effekt lägger vi till i user_effects. Här kollar vi bara om effekten är tillåten.
    # För enkelhet: alla effekter är tillgängliga om användaren har köpt dem via butiken.
    # Vi validerar mot users.active_effects
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT active_effects, coins FROM users WHERE username = ?", (username,))
    user_row = c.fetchone()
    if not user_row:
        # Skapa ny användare om den inte finns (borde finnas efter login)
        conn.close()
        return jsonify({"error": "Användare ej registrerad"}), 400
    active_effects = json.loads(user_row['active_effects']) if user_row['active_effects'] else []
    if effect and effect not in [e['name'] for e in active_effects]:
        return jsonify({"error": "Du äger inte den effekten"}), 400
    
    post_id = uuid.uuid4().hex
    new_post = {
        "id": post_id,
        "title": data["title"],
        "author": "Anonym" if is_anonymous else username,
        "anonymous": is_anonymous,
        "content": data["content"],
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "likes": 0,
        "liked_by": [],
        "vip": is_vip,
        "images": images,
        "comments": [],
        "effect": effect
    }
    
    c.execute('''INSERT INTO posts 
                 (id, title, author, anonymous, content, date, likes, liked_by, vip, images, comments, effect)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (post_id, new_post['title'], new_post['author'], int(new_post['anonymous']),
               new_post['content'], new_post['date'], new_post['likes'],
               json.dumps(new_post['liked_by']), int(new_post['vip']),
               json.dumps(new_post['images']), json.dumps(new_post['comments']), new_post['effect']))
    
    # Uppdatera användarens stats
    c.execute("UPDATE users SET total_posts = total_posts + 1, last_post_time = ? WHERE username = ?", (datetime.now().isoformat(), username))
    conn.commit()
    conn.close()
    
    # Ge XP och coins
    add_xp(username, 20)
    add_coins(username, 10)
    
    return jsonify({"message": "Ryktet publicerat!", "id": post_id})

@app.route('/posts/<post_id>/like', methods=['POST'])
def like_post(post_id):
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Ange användarnamn"}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT likes, liked_by, author FROM posts WHERE id = ?", (post_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Inlägg finns inte"}), 404
    
    liked_by = json.loads(row[1]) if row[1] else []
    if username in liked_by:
        conn.close()
        return jsonify({"message": "Redan gillat"}), 200
    
    new_likes = row[0] + 1
    liked_by.append(username)
    c.execute("UPDATE posts SET likes = ?, liked_by = ? WHERE id = ?",
              (new_likes, json.dumps(liked_by), post_id))
    conn.commit()
    
    # Ge XP och coins till skaparen av ryktet (om inte anonymt och inte sig själv)
    post_author = row[2]
    if post_author != "Anonym" and post_author != username:
        add_xp(post_author, 2)
        add_coins(post_author, 1)
    # Ge lite XP till den som gillar
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
    
    comment = {
        "username": username,
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT comments, author FROM posts WHERE id = ?", (post_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Inlägg finns inte"}), 404
    
    comments = json.loads(row[0]) if row[0] else []
    comments.append(comment)
    c.execute("UPDATE posts SET comments = ? WHERE id = ?", (json.dumps(comments), post_id))
    conn.commit()
    
    # Ge XP och coins till skaparen
    post_author = row[1]
    if post_author != "Anonym" and post_author != username:
        add_xp(post_author, 1)
        add_coins(post_author, 2)
    # Ge XP till kommenteraren
    add_xp(username, 1)
    add_coins(username, 1)
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

# ---------- ANVÄNDAR-RELATERADE ENDPOINTS ----------
@app.route('/user/<username>', methods=['GET'])
def get_user(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT username, level, xp, coins, total_posts, total_likes_received, total_comments, login_streak, active_effects FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Användare finns ej"}), 404
    user = dict(row)
    user['active_effects'] = json.loads(user['active_effects']) if user['active_effects'] else []
    # Beräkna XP till nästa level
    next_xp = xp_for_next_level(user['xp'])
    user['xp_to_next'] = next_xp - user['xp'] if next_xp else 0
    conn.close()
    return jsonify(user)

@app.route('/user/<username>/daily', methods=['POST'])
def daily_bonus(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT last_login_date, login_streak FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Användare finns ej"}), 404
    today = datetime.now().date().isoformat()
    last_login = row['last_login_date']
    streak = row['login_streak'] if row['login_streak'] else 0
    if last_login == today:
        conn.close()
        return jsonify({"message": "Du har redan fått dagens bonus!"}), 200
    # Beräkna ny streak
    if last_login:
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        if last_login == yesterday:
            streak += 1
        else:
            streak = 1
    else:
        streak = 1
    bonus = 5 + streak  # 5 + streak extra
    c.execute("UPDATE users SET coins = coins + ?, login_streak = ?, last_login_date = ? WHERE username = ?",
              (bonus, streak, today, username))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Daglig bonus: {bonus} coins!", "streak": streak})

@app.route('/shop', methods=['GET'])
def get_shop():
    items = [
        {"id": "fire_glow", "name": "🔥 Fire Glow", "price": 100, "duration_days": 7, "description": "Röd-orange glow runt ryktet"},
        {"id": "diamond_glow", "name": "💎 Diamond Glow", "price": 250, "duration_days": 7, "description": "Blått pulserande glow"},
        {"id": "royal_crown", "name": "👑 Royal Crown", "price": 500, "duration_days": 14, "description": "Guldglow + krona i titeln"},
        {"id": "sparkle", "name": "✨ Sparkle", "price": 150, "duration_days": 7, "description": "Stjärnor som faller runt kortet"},
        {"id": "rainbow", "name": "🌈 Rainbow Border", "price": 300, "duration_days": 7, "description": "Regnbågsfärgad border"},
        {"id": "pin_to_top", "name": "📌 Pin to Top (1h)", "price": 400, "duration_days": 0, "description": "Ryktet hamnar överst i 1 timme"},
        {"id": "mystery", "name": "🎁 Mystery Box", "price": 75, "duration_days": 7, "description": "Slumpmässig effekt"},
        {"id": "lock_post", "name": "🔒 Lock Post", "price": 600, "duration_days": 0, "description": "Kan inte tas bort av vanliga användare"}
    ]
    return jsonify(items)

@app.route('/shop/buy', methods=['POST'])
def buy_effect():
    data = request.get_json()
    username = data.get("username")
    effect_id = data.get("effect_id")
    if not username or not effect_id:
        return jsonify({"error": "Saknas uppgifter"}), 400
    
    # Hämta butiksobjekt
    items = [
        {"id": "fire_glow", "name": "🔥 Fire Glow", "price": 100, "duration_days": 7},
        {"id": "diamond_glow", "name": "💎 Diamond Glow", "price": 250, "duration_days": 7},
        {"id": "royal_crown", "name": "👑 Royal Crown", "price": 500, "duration_days": 14},
        {"id": "sparkle", "name": "✨ Sparkle", "price": 150, "duration_days": 7},
        {"id": "rainbow", "name": "🌈 Rainbow Border", "price": 300, "duration_days": 7},
        {"id": "pin_to_top", "name": "📌 Pin to Top (1h)", "price": 400, "duration_days": 0},
        {"id": "mystery", "name": "🎁 Mystery Box", "price": 75, "duration_days": 7},
        {"id": "lock_post", "name": "🔒 Lock Post", "price": 600, "duration_days": 0}
    ]
    effect = next((e for e in items if e['id'] == effect_id), None)
    if not effect:
        return jsonify({"error": "Effekt finns inte"}), 404
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT coins, active_effects FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Användare ej funnen"}), 404
    if user['coins'] < effect['price']:
        conn.close()
        return jsonify({"error": "Inte tillräckligt med coins"}), 400
    
    # Lägg till effekt i active_effects (lista med dict)
    active = json.loads(user['active_effects']) if user['active_effects'] else []
    expires_at = None
    if effect['duration_days'] > 0:
        expires_at = (datetime.now() + timedelta(days=effect['duration_days'])).isoformat()
    active.append({
        "name": effect['id'],
        "purchased_at": datetime.now().isoformat(),
        "expires_at": expires_at
    })
    new_coins = user['coins'] - effect['price']
    c.execute("UPDATE users SET coins = ?, active_effects = ? WHERE username = ?",
              (new_coins, json.dumps(active), username))
    # Logga transaktion
    trans_id = uuid.uuid4().hex
    c.execute("INSERT INTO transactions (id, username, effect_name, coins_spent, purchase_date, expires_at) VALUES (?,?,?,?,?,?)",
              (trans_id, username, effect['name'], effect['price'], datetime.now().isoformat(), expires_at))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Du köpte {effect['name']}!", "new_coins": new_coins})

@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    conn = get_db()
    c = conn.cursor()
    # Topplista baserad på level och XP
    c.execute("SELECT username, level, xp, coins FROM users ORDER BY level DESC, xp DESC LIMIT 10")
    rows = c.fetchall()
    leader = [dict(row) for row in rows]
    conn.close()
    return jsonify(leader)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    # Hämta giltiga inloggningar från GitHub (hårdkodad för demo, men du kan anropa GitHub)
    # För enkelhet, använd samma som tidigare: läs från raw URL
    import requests
    try:
        resp = requests.get('https://raw.githubusercontent.com/Gelatex/xxsfaf241i3b4/main/logins')
        if resp.status_code == 200:
            lines = resp.text.strip().split()
            valid = {}
            for line in lines:
                if ':' in line:
                    u, p = line.split(':')
                    valid[u] = p
        else:
            valid = {"Ebbe":"Samson123","Eskil":"Kevzter10","Pyttevalen":"Cosmo123"}
    except:
        valid = {"Ebbe":"Samson123","Eskil":"Kevzter10","Pyttevalen":"Cosmo123"}
    
    if username in valid and valid[username] == password:
        # Skapa användare om den inte finns
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        if not c.fetchone():
            c.execute("INSERT INTO users (username, level, xp, coins, last_login_date) VALUES (?,1,0,50,?)",
                      (username, datetime.now().date().isoformat()))
            conn.commit()
        conn.close()
        return jsonify({"success": True, "username": username})
    return jsonify({"success": False}), 401

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
