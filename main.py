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

# GitHub-konfiguration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = "Gelatex"
REPO_NAME = "xxsfaf241i3b4"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# ---------------------------
# Hjälpfunktioner för GitHub-filer
# ---------------------------
def get_github_file(path):
    """Hämta innehåll och SHA för en fil från GitHub"""
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
    """Uppdatera eller skapa en fil på GitHub"""
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
    """Läs en JSON-fil från GitHub, returnera default om den inte finns"""
    content, sha = get_github_file(path)
    if content is None:
        return default if default is not None else {}, sha
    try:
        return json.loads(content), sha
    except:
        return default if default is not None else {}, sha

def write_json_file(path, data, sha=None):
    """Skriv ett Python-objekt som JSON till GitHub"""
    content = json.dumps(data, indent=2, ensure_ascii=False)
    update_github_file(path, content, sha)

# ---------------------------
# Inloggningshantering (som tidigare)
# ---------------------------
def get_logins():
    content, _ = get_github_file("logins")
    if not content:
        return {}
    logins = {}
    for line in content.splitlines():
        if ':' in line:
            u, p = line.strip().split(':', 1)
            logins[u] = p
    return logins

def save_logins(logins):
    content = "\n".join([f"{u}:{p}" for u, p in logins.items()])
    _, sha = get_github_file("logins")
    update_github_file("logins", content, sha)

# ---------------------------
# Användardata (XP, level, coins, last_rumor_time)
# ---------------------------
def get_users_data():
    data, _ = read_json_file("users_data.json", {})
    return data

def save_users_data(data):
    _, sha = get_github_file("users_data.json")
    write_json_file("users_data.json", data, sha)

def get_user_profile(username):
    users = get_users_data()
    if username not in users:
        users[username] = {
            "xp": 0,
            "level": 1,
            "coins": 0,
            "last_rumor_time": 0  # timestamp för senaste ryktet
        }
        save_users_data(users)
    return users[username]

def update_user_xp(username, xp_gain):
    users = get_users_data()
    if username not in users:
        users[username] = {"xp": 0, "level": 1, "coins": 0, "last_rumor_time": 0}
    old_level = users[username]["level"]
    users[username]["xp"] += xp_gain
    # Beräkna ny level: var 100 XP = +1 level
    new_level = 1 + (users[username]["xp"] // 100)
    users[username]["level"] = new_level
    # Bonus coins vid levelup
    if new_level > old_level:
        coins_gain = (new_level - old_level) * 5
        users[username]["coins"] += coins_gain
    save_users_data(users)
    return users[username]

def add_coins(username, amount):
    users = get_users_data()
    if username not in users:
        users[username] = {"xp": 0, "level": 1, "coins": 0, "last_rumor_time": 0}
    users[username]["coins"] += amount
    save_users_data(users)

# ---------------------------
# Rykten (stuffs) – sparas i rumors.json
# ---------------------------
def get_rumors():
    data, _ = read_json_file("rumors.json", [])
    return data

def save_rumors(rumors):
    _, sha = get_github_file("rumors.json")
    write_json_file("rumors.json", rumors, sha)

def create_rumor(author, title, content):
    rumors = get_rumors()
    new_rumor = {
        "id": int(time.time() * 1000),  # unikt ID baserat på millisekunder
        "author": author,
        "title": title,
        "content": content,
        "date": datetime.now().isoformat(),
        "likes": 0,
        "liked_by": [],  # lista över användarnamn som gillat
        "comments": []    # varje kommentar: {"user": "xxx", "text": "yyy", "date": "..."}
    }
    rumors.insert(0, new_rumor)  # nyaste först
    save_rumors(rumors)
    return new_rumor

def like_rumor(rumor_id, username):
    rumors = get_rumors()
    for r in rumors:
        if r["id"] == rumor_id:
            if username in r.get("liked_by", []):
                return False, "Du har redan gillat detta rykte"
            r["likes"] = r.get("likes", 0) + 1
            if "liked_by" not in r:
                r["liked_by"] = []
            r["liked_by"].append(username)
            save_rumors(rumors)
            return True, "Gillade!"
    return False, "Rykte finns inte"

def add_comment(rumor_id, username, text):
    rumors = get_rumors()
    for r in rumors:
        if r["id"] == rumor_id:
            comment = {
                "user": username,
                "text": text,
                "date": datetime.now().isoformat()
            }
            r.setdefault("comments", []).append(comment)
            save_rumors(rumors)
            return True, "Kommentar tillagd"
    return False, "Rykte finns inte"

# ---------------------------
# API-endpoints
# ---------------------------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    logins = get_logins()
    if username in logins and logins[username] == password:
        # Se till att användaren finns i users_data
        get_user_profile(username)
        return jsonify({"success": True, "message": "Inloggning lyckades"})
    return jsonify({"success": False, "message": "Fel användarnamn eller lösenord"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if len(username) < 3 or len(password) < 4:
        return jsonify({"success": False, "message": "Användarnamn minst 3 tecken, lösenord minst 4"}), 400
    logins = get_logins()
    if username in logins:
        return jsonify({"success": False, "message": "Användarnamnet finns redan"}), 409
    logins[username] = password
    save_logins(logins)
    # Skapa användarprofil
    get_user_profile(username)
    return jsonify({"success": True, "message": "Konto skapat!"})

@app.route('/user_data', methods=['GET'])
def user_data():
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "Username required"}), 400
    profile = get_user_profile(username)
    return jsonify(profile)

@app.route('/rumors', methods=['GET'])
def rumors():
    return jsonify(get_rumors())

@app.route('/create_rumor', methods=['POST'])
def create_rumor_endpoint():
    data = request.get_json()
    username = data.get('username')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    if not username or not title or not content:
        return jsonify({"success": False, "message": "Alla fält krävs"}), 400
    # Cooldown-koll
    profile = get_user_profile(username)
    level = profile["level"]
    cooldown_seconds = max(10, 60 - (level-1) * 2)  # level 1:60s, level 25: max 10s
    last_time = profile.get("last_rumor_time", 0)
    now = time.time()
    if now - last_time < cooldown_seconds:
        remaining = int(cooldown_seconds - (now - last_time))
        return jsonify({"success": False, "message": f"Vänta {remaining} sekunder innan nästa rykte"}), 429
    # Skapa ryktet
    rumor = create_rumor(username, title, content)
    # Uppdatera last_rumor_time och ge XP + coins
    users = get_users_data()
    users[username]["last_rumor_time"] = now
    save_users_data(users)
    update_user_xp(username, 10)      # 10 XP för att skapa rykte
    add_coins(username, 1)            # 1 coin per rykte
    return jsonify({"success": True, "rumor": rumor})

@app.route('/like_rumor', methods=['POST'])
def like_rumor_endpoint():
    data = request.get_json()
    username = data.get('username')
    rumor_id = data.get('rumor_id')
    if not username or not rumor_id:
        return jsonify({"success": False, "message": "Saknas data"}), 400
    ok, msg = like_rumor(rumor_id, username)
    if ok:
        update_user_xp(username, 1)  # 1 XP för like
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/comment_rumor', methods=['POST'])
def comment_rumor_endpoint():
    data = request.get_json()
    username = data.get('username')
    rumor_id = data.get('rumor_id')
    text = data.get('text', '').strip()
    if not username or not rumor_id or not text:
        return jsonify({"success": False, "message": "Saknas data"}), 400
    ok, msg = add_comment(rumor_id, username, text)
    if ok:
        update_user_xp(username, 2)  # 2 XP för kommentar
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
