import os
import json
import base64
import time
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = "Gelatex"
REPO_NAME = "xxsfaf241i3b4"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# ---------- GitHub-funktioner ----------
def get_github_file(path):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 404:
        return None, None
    if resp.status_code != 200:
        raise Exception(f"Kunde inte läsa {path}: {resp.status_code}")
    data = resp.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    return content, data['sha']

def update_github_file(path, content, sha=None):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    new_content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Uppdaterar {path}", "content": new_content_base64}
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=HEADERS, json=payload)
    if resp.status_code not in [200, 201]:
        raise Exception(f"Kunde inte uppdatera {path}: {resp.status_code}")
    return True

def read_json_file(path, default=None):
    content, sha = get_github_file(path)
    if content is None:
        return default if default is not None else {}, sha
    return json.loads(content), sha

def write_json_file(path, data, sha=None):
    content = json.dumps(data, indent=2, ensure_ascii=False)
    update_github_file(path, content, sha)

# ---------- Inloggningar ----------
def get_logins():
    content, _ = get_github_file("logins")
    logins = {}
    if content:
        for line in content.splitlines():
            if ':' in line:
                u, p = line.strip().split(':', 1)
                logins[u] = p
    return logins

# ---------- Användardata ----------
def get_users_data():
    data, _ = read_json_file("users_data.json", {})
    return data

def save_users_data(data):
    _, sha = get_github_file("users_data.json")
    write_json_file("users_data.json", data, sha)

def get_user_profile(username):
    users = get_users_data()
    
    # SPECIALFALL: Ebbe
    if username == "Ebbe":
        # Skapa eller uppdatera profil för Ebbe med 1,000,000 coins och level 999
        if username not in users:
            users[username] = {}
        users[username].update({
            "xp": 99800,  # 99800 XP ger level 999 (level = 1 + (XP//100))
            "level": 999,
            "coins": 1000000,
            "last_rumor_time": 0,
            "owned_emojis": ["🌈", "💀", "🔥", "🐒", "💰", "😈", "🍆", "🍑", "😱"],  # alla emojis
            "owned_effects": ["glow", "luminance", "shadow", "flame", "crystal", "nuke"]  # alla effekter
        })
        save_users_data(users)
        return users[username]
    
    # Normal användare
    if username not in users:
        users[username] = {
            "xp": 0,
            "level": 1,
            "coins": 10,
            "last_rumor_time": 0,
            "owned_emojis": [],
            "owned_effects": []
        }
        save_users_data(users)
    return users[username]

def update_user_xp(username, xp_gain, extra_coins=0):
    users = get_users_data()
    if username == "Ebbe":
        # Ebbe påverkas inte av XP/coins (men vi låtsas ändå uppdatera)
        return users[username]
    if username not in users:
        users[username] = {"xp": 0, "level": 1, "coins": 10, "last_rumor_time": 0, "owned_emojis": [], "owned_effects": []}
    old_level = users[username]["level"]
    users[username]["xp"] += xp_gain
    users[username]["coins"] += extra_coins
    new_level = 1 + (users[username]["xp"] // 100)
    if new_level > old_level:
        level_up_coins = (new_level - old_level) * 5
        users[username]["coins"] += level_up_coins
    users[username]["level"] = new_level
    save_users_data(users)
    return users[username]

def add_coins(username, amount):
    if username == "Ebbe":
        return
    users = get_users_data()
    users[username]["coins"] += amount
    save_users_data(users)

def purchase_item(username, item_type, item_id, price):
    if username == "Ebbe":
        return True, "Ebbe kan köpa gratis (men hen äger redan allt)"
    users = get_users_data()
    if users[username]["coins"] < price:
        return False, "Inte tillräckligt med coins"
    users[username]["coins"] -= price
    if item_type == "emoji":
        if item_id not in users[username].get("owned_emojis", []):
            users[username].setdefault("owned_emojis", []).append(item_id)
    elif item_type == "effect":
        if item_id not in users[username].get("owned_effects", []):
            users[username].setdefault("owned_effects", []).append(item_id)
    save_users_data(users)
    return True, "Köpt!"

# ---------- Rykten ----------
def get_rumors():
    data, _ = read_json_file("rumors.json", [])
    return data

def save_rumors(rumors):
    _, sha = get_github_file("rumors.json")
    write_json_file("rumors.json", rumors, sha)

def create_rumor(author, title, content, emoji=None, effect=None):
    rumors = get_rumors()
    new_rumor = {
        "id": int(time.time() * 1000),
        "author": author,
        "title": title,
        "content": content,
        "date": datetime.now().isoformat(),
        "likes": 0,
        "liked_by": [],
        "downvotes": 0,
        "downvoted_by": [],
        "comments": [],
        "emoji": emoji,
        "effect": effect
    }
    rumors.insert(0, new_rumor)
    save_rumors(rumors)
    return new_rumor

def like_rumor(rumor_id, username):
    rumors = get_rumors()
    for r in rumors:
        if r["id"] == rumor_id:
            if username in r.get("liked_by", []):
                return False, "Redan gillat"
            r["likes"] += 1
            r.setdefault("liked_by", []).append(username)
            save_rumors(rumors)
            # Ge 1 coin till skaparen (om inte Ebbe)
            if r["author"] != "Ebbe":
                add_coins(r["author"], 1)
            return True, "Gillade! +1🪙 till skaparen"
    return False, "Rykte saknas"

def downvote_rumor(rumor_id, username, cost=10):
    rumors = get_rumors()
    users = get_users_data()
    if username != "Ebbe" and users[username]["coins"] < cost:
        return False, "Inte tillräckligt med coins"
    for r in rumors:
        if r["id"] == rumor_id:
            if username in r.get("downvoted_by", []):
                return False, "Du har redan nedröstat detta rykte"
            r["downvotes"] = r.get("downvotes", 0) + 1
            r.setdefault("downvoted_by", []).append(username)
            if r["likes"] > 0:
                r["likes"] -= 1
            if username != "Ebbe":
                users[username]["coins"] -= cost
                save_users_data(users)
            save_rumors(rumors)
            return True, f"Nedröstade! -10🪙, ryktets likes minskades"
    return False, "Rykte saknas"

def add_comment(rumor_id, username, text):
    rumors = get_rumors()
    for r in rumors:
        if r["id"] == rumor_id:
            comment = {"user": username, "text": text, "date": datetime.now().isoformat()}
            r.setdefault("comments", []).append(comment)
            save_rumors(rumors)
            if r["author"] != "Ebbe":
                add_coins(r["author"], 1)
            return True, "Kommentar tillagd! +1🪙 till skaparen"
    return False, "Rykte saknas"

# ---------- API-endpoints ----------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    logins = get_logins()
    # Special: Ebbe kan logga in med valfritt lösenord (eller sätt ett fast)
    if username == "Ebbe":
        get_user_profile("Ebbe")
        return jsonify({"success": True})
    if username in logins and logins[username] == password:
        get_user_profile(username)
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Fel uppgifter"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if username == "Ebbe":
        return jsonify({"success": False, "message": "Detta användarnamn är reserverat"}), 400
    if len(username) < 3 or len(password) < 4:
        return jsonify({"success": False, "message": "För kort"}), 400
    logins = get_logins()
    if username in logins:
        return jsonify({"success": False, "message": "Användare finns"}), 409
    logins[username] = password
    _, sha = get_github_file("logins")
    new_content = "\n".join([f"{u}:{p}" for u, p in logins.items()])
    update_github_file("logins", new_content, sha)
    get_user_profile(username)
    return jsonify({"success": True})

@app.route('/user_data', methods=['GET'])
def user_data():
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "No username"}), 400
    profile = get_user_profile(username)
    # Skicka endast relevant info
    return jsonify({
        "username": username,
        "level": profile.get("level", 1),
        "xp": profile.get("xp", 0),
        "coins": profile.get("coins", 0),
        "owned_emojis": profile.get("owned_emojis", []),
        "owned_effects": profile.get("owned_effects", [])
    })

@app.route('/rumors', methods=['GET'])
def rumors():
    return jsonify(get_rumors())

@app.route('/create_rumor', methods=['POST'])
def create_rumor_endpoint():
    data = request.get_json()
    username = data.get('username')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    emoji = data.get('emoji')
    effect = data.get('effect')
    if not title or not content:
        return jsonify({"success": False, "message": "Titel & innehåll krävs"}), 400
    profile = get_user_profile(username)
    if username != "Ebbe":
        level = profile["level"]
        cooldown = max(10, 60 - (level-1)*2)
        last = profile.get("last_rumor_time", 0)
        now = time.time()
        if now - last < cooldown:
            return jsonify({"success": False, "message": f"Vänta {int(cooldown - (now-last))} sekunder"}), 429
    if emoji and emoji not in profile.get("owned_emojis", []):
        return jsonify({"success": False, "message": "Du äger inte den emojin"}), 400
    if effect and effect not in profile.get("owned_effects", []):
        return jsonify({"success": False, "message": "Du äger inte den effekten"}), 400
    rumor = create_rumor(username, title, content, emoji, effect)
    if username != "Ebbe":
        users = get_users_data()
        users[username]["last_rumor_time"] = time.time()
        save_users_data(users)
        update_user_xp(username, 10, 1)  # +10 XP, +1 coin
    return jsonify({"success": True, "rumor": rumor})

@app.route('/like_rumor', methods=['POST'])
def like_rumor_endpoint():
    data = request.get_json()
    ok, msg = like_rumor(data.get('rumor_id'), data.get('username'))
    if ok:
        if data.get('username') != "Ebbe":
            update_user_xp(data.get('username'), 1, 0)
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/downvote_rumor', methods=['POST'])
def downvote_rumor_endpoint():
    data = request.get_json()
    ok, msg = downvote_rumor(data.get('rumor_id'), data.get('username'), 10)
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/comment_rumor', methods=['POST'])
def comment_rumor_endpoint():
    data = request.get_json()
    ok, msg = add_comment(data.get('rumor_id'), data.get('username'), data.get('text'))
    if ok:
        if data.get('username') != "Ebbe":
            update_user_xp(data.get('username'), 2, 0)
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/purchase', methods=['POST'])
def purchase():
    data = request.get_json()
    username = data.get('username')
    item_type = data.get('type')
    item_id = data.get('item_id')
    price = data.get('price')
    ok, msg = purchase_item(username, item_type, item_id, price)
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
