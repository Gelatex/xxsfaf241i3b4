import os
import json
import time
import base64
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ---------- GITHUB ----------
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = "Gelatex"
REPO_NAME = "xxsfaf241i3b4"

def github_request(method, path, data=None):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    if method == 'GET':
        resp = requests.get(url, headers=headers)
    else:
        resp = requests.put(url, headers=headers, json=data)
    return resp

def read_github_json(filepath):
    """Läser en JSON‑fil från GitHub, returnerar (data, sha). Skapar filen om den saknas."""
    resp = github_request('GET', filepath)
    if resp.status_code == 404:
        # Filen finns inte – skapa tom fil
        default_content = "[]" if "rykten" in filepath else "{}"
        create_resp = github_request('PUT', filepath, {
            "message": f"Skapa {filepath}",
            "content": base64.b64encode(default_content.encode()).decode()
        })
        if create_resp.status_code == 201:
            return json.loads(default_content), create_resp.json()['content']['sha']
        else:
            raise Exception(f"Kunde inte skapa {filepath}")
    elif resp.status_code == 200:
        data = resp.json()
        content = base64.b64decode(data['content']).decode('utf-8')
        return json.loads(content), data['sha']
    else:
        raise Exception(f"GitHub fel {resp.status_code}: {resp.text}")

def write_github_json(filepath, data, sha):
    """Skriver JSON‑data till GitHub."""
    new_content = json.dumps(data, indent=2, ensure_ascii=False)
    encoded = base64.b64encode(new_content.encode()).decode()
    payload = {
        "message": f"Uppdaterar {filepath}",
        "content": encoded,
        "sha": sha
    }
    resp = github_request('PUT', filepath, payload)
    if resp.status_code not in (200, 201):
        raise Exception(f"Kunde inte skriva {filepath}: {resp.status_code}")

# ---------- HJÄLPFUNKTIONER ----------
def get_users_data():
    """Returnerar dict {användarnamn: {level, xp, coins, last_post_time, effects}}"""
    data, sha = read_github_json("stuffs/users_data.json")
    return data, sha

def save_users_data(data, sha):
    write_github_json("stuffs/users_data.json", data, sha)

def get_rykten_data():
    """Returnerar lista med alla rykten {id, author, title, content, likes, comments, timestamp}"""
    data, sha = read_github_json("stuffs/rykten.json")
    return data, sha

def save_rykten_data(data, sha):
    write_github_json("stuffs/rykten.json", data, sha)

def get_login_content():
    """Läser inloggningsfilen för validering (befintlig kod)"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/logins"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return ""
    data = resp.json()
    return base64.b64decode(data['content']).decode('utf-8')

def check_login(username, password):
    content = get_login_content()
    for line in content.splitlines():
        if ':' in line:
            u, p = line.strip().split(':', 1)
            if u == username and p == password:
                return True
    return False

def init_user_data(username):
    """Skapar en ny användare i users_data.json om den inte finns."""
    data, sha = get_users_data()
    if username not in data:
        data[username] = {
            "level": 1,
            "xp": 0,
            "coins": 50,      # startcoins
            "last_post_time": 0,
            "effects": []     # list av aktiva effekter
        }
        save_users_data(data, sha)

def calculate_level(xp):
    """Level = 1 + floor(xp/100)"""
    return 1 + (xp // 100)

def add_xp(username, amount):
    """Lägger till XP, räknar om level, ger coins vid level‑up."""
    data, sha = get_users_data()
    if username not in data:
        init_user_data(username)
        data, sha = get_users_data()
    old_level = data[username]["level"]
    data[username]["xp"] += amount
    new_level = calculate_level(data[username]["xp"])
    if new_level > old_level:
        # Level‑up! Ge coins (10 per ny level)
        coins_gained = (new_level - old_level) * 10
        data[username]["coins"] += coins_gained
    data[username]["level"] = new_level
    save_users_data(data, sha)
    return new_level - old_level  # antal level‑ups

def get_cooldown_seconds(username):
    """Cooldown = max(10, 60 - level*2)"""
    data, _ = get_users_data()
    if username not in data:
        return 60
    level = data[username]["level"]
    return max(10, 60 - level * 2)

# ---------- ROUTES ----------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"success": False, "message": "Användarnamn och lösenord krävs"}), 400
    if check_login(username, password):
        init_user_data(username)  # säkerställer att användaren finns i users_data
        return jsonify({"success": True, "message": "Inloggning lyckades"})
    return jsonify({"success": False, "message": "Fel användarnamn eller lösenord"}), 401

@app.route('/dashboard', methods=['GET'])
def dashboard():
    username = request.args.get('username')
    if not username:
        return jsonify({"success": False, "message": "Användarnamn saknas"}), 400
    # Hämta användardata
    users, _ = get_users_data()
    user = users.get(username)
    if not user:
        return jsonify({"success": False, "message": "Användare hittades inte"}), 404
    # Hämta alla rykten
    rykten, _ = get_rykten_data()
    # Beräkna återstående cooldown
    last_post = user.get("last_post_time", 0)
    cooldown = get_cooldown_seconds(username)
    remaining = max(0, cooldown - (time.time() - last_post))
    return jsonify({
        "success": True,
        "user": {
            "username": username,
            "level": user["level"],
            "xp": user["xp"],
            "coins": user["coins"],
            "next_level_xp": (user["level"] * 100),
            "cooldown_seconds": cooldown,
            "remaining_cooldown": remaining,
            "effects": user.get("effects", [])
        },
        "rykten": rykten
    })

@app.route('/create_rykte', methods=['POST'])
def create_rykte():
    data = request.get_json()
    username = data.get('username')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    if not title or not content:
        return jsonify({"success": False, "message": "Titel och innehåll krävs"}), 400
    # Kolla cooldown
    users, users_sha = get_users_data()
    if username not in users:
        return jsonify({"success": False, "message": "Användare okänd"}), 404
    last_post = users[username].get("last_post_time", 0)
    cooldown = get_cooldown_seconds(username)
    if time.time() - last_post < cooldown:
        return jsonify({"success": False, "message": f"Du måste vänta {int(cooldown - (time.time() - last_post))} sekunder"}), 429
    # Skapa nytt rykte
    rykten, rykten_sha = get_rykten_data()
    new_id = 1
    if rykten:
        new_id = max(r['id'] for r in rykten) + 1
    new_rykte = {
        "id": new_id,
        "author": username,
        "title": title,
        "content": content,
        "likes": 0,
        "comments": [],
        "timestamp": time.time()
    }
    rykten.append(new_rykte)
    save_rykten_data(rykten, rykten_sha)
    # Uppdatera last_post_time och ge XP
    users[username]["last_post_time"] = time.time()
    save_users_data(users, users_sha)
    # Ge 10 XP för att skapa rykte
    add_xp(username, 10)
    return jsonify({"success": True, "message": "Rykte publicerat!", "rykte_id": new_id})

@app.route('/like', methods=['POST'])
def like():
    data = request.get_json()
    username = data.get('username')
    ryktes_id = data.get('rykte_id')
    if not username or not ryktes_id:
        return jsonify({"success": False, "message": "Saknas data"}), 400
    rykten, rykten_sha = get_rykten_data()
    for r in rykten:
        if r['id'] == ryktes_id:
            r['likes'] += 1
            save_rykten_data(rykten, rykten_sha)
            # Ge författaren 5 XP
            author = r['author']
            if author != username:  # man får inte XP för att gilla sitt eget
                add_xp(author, 5)
            return jsonify({"success": True, "message": "Du gillade ryktet!"})
    return jsonify({"success": False, "message": "Rykte hittades inte"}), 404

@app.route('/comment', methods=['POST'])
def comment():
    data = request.get_json()
    username = data.get('username')
    ryktes_id = data.get('rykte_id')
    comment_text = data.get('comment', '').strip()
    if not comment_text:
        return jsonify({"success": False, "message": "Kommentaren är tom"}), 400
    rykten, rykten_sha = get_rykten_data()
    for r in rykten:
        if r['id'] == ryktes_id:
            r['comments'].append({"user": username, "text": comment_text, "timestamp": time.time()})
            save_rykten_data(rykten, rykten_sha)
            # Ge författaren 2 XP
            author = r['author']
            if author != username:
                add_xp(author, 2)
            return jsonify({"success": True, "message": "Kommentar tillagd!"})
    return jsonify({"success": False, "message": "Rykte hittades inte"}), 404

@app.route('/buy_effect', methods=['POST'])
def buy_effect():
    data = request.get_json()
    username = data.get('username')
    effect = data.get('effect')
    price = 0
    effects_prices = {
        "double_xp": 30,
        "cooldown_half": 50
    }
    if effect not in effects_prices:
        return jsonify({"success": False, "message": "Ogiltig effekt"}), 400
    price = effects_prices[effect]
    users, sha = get_users_data()
    if username not in users:
        return jsonify({"success": False, "message": "Användare okänd"}), 404
    if users[username]["coins"] < price:
        return jsonify({"success": False, "message": "För få coins"}), 400
    users[username]["coins"] -= price
    if "effects" not in users[username]:
        users[username]["effects"] = []
    # Effekter varar i 1 timme (3600 sekunder)
    expiry = time.time() + 3600
    users[username]["effects"].append({"type": effect, "expires": expiry})
    save_users_data(users, sha)
    return jsonify({"success": True, "message": f"Effekt {effect} köpt! Varar 1 timme."})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
