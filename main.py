import os
import json
import base64
import time
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# ---------- GitHub-konfiguration ----------
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = "Gelatex"
REPO_NAME = "xxsfaf241i3b4"

def github_request(method, path, data=None):
    """Gör anrop till GitHub API"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    if method == 'GET':
        resp = requests.get(url, headers=headers)
    elif method == 'PUT':
        resp = requests.put(url, headers=headers, json=data)
    else:
        raise Exception("Unsupported method")
    
    if resp.status_code not in [200, 201]:
        # Om filen inte finns, returnera None
        if resp.status_code == 404:
            return None
        raise Exception(f"GitHub API error {resp.status_code}: {resp.text}")
    return resp.json()

def read_github_json(filename, default=None):
    """Läs JSON-fil från GitHub, returnera default om den inte finns"""
    try:
        result = github_request('GET', filename)
        if result is None:
            return default if default is not None else {}
        content = base64.b64decode(result['content']).decode('utf-8')
        return json.loads(content)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return default if default is not None else {}

def write_github_json(filename, data, message="Update"):
    """Skriv JSON-data till GitHub"""
    # Först hämta nuvarande fil (för SHA)
    existing = None
    try:
        existing = github_request('GET', filename)
    except:
        pass
    
    content = json.dumps(data, indent=2, ensure_ascii=False)
    content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": message,
        "content": content_base64
    }
    if existing and 'sha' in existing:
        payload['sha'] = existing['sha']
    
    return github_request('PUT', filename, payload)

# ---------- Hjälpfunktioner för användare ----------
def get_users_data():
    """Hämta användardata (level, xp, coins, cooldown)"""
    default = {}
    data = read_github_json('users_data.json', default)
    # Säkerställ att alla fält finns för varje användare
    for username, info in data.items():
        if 'level' not in info:
            info['level'] = 1
        if 'xp' not in info:
            info['xp'] = 0
        if 'coins' not in info:
            info['coins'] = 50  # startcoins
        if 'last_rumor_time' not in info:
            info['last_rumor_time'] = 0
    return data

def save_users_data(data):
    write_github_json('users_data.json', data, "Update users data")

def add_xp(username, amount):
    """Lägg till XP, hantera level-ups"""
    users = get_users_data()
    if username not in users:
        users[username] = {"level": 1, "xp": 0, "coins": 50, "last_rumor_time": 0}
    users[username]['xp'] += amount
    # Level-up: varje level kräver 100 * level XP
    old_level = users[username]['level']
    new_level = old_level
    while users[username]['xp'] >= new_level * 100:
        users[username]['xp'] -= new_level * 100
        new_level += 1
        users[username]['coins'] += 50  # bonus coins vid level-up
    if new_level > old_level:
        users[username]['level'] = new_level
    save_users_data(users)
    return users[username]

def get_cooldown_seconds(level):
    """Cooldown i sekunder: level 1 = 60s, level 5 = 30s, level 10 = 10s"""
    if level >= 10:
        return 10
    elif level >= 5:
        return 30
    else:
        return 60

# ---------- Inloggningskoll (logins-fil) ----------
def check_login(username, password):
    try:
        result = github_request('GET', 'logins')
        if result is None:
            return False
        content = base64.b64decode(result['content']).decode('utf-8')
        for line in content.splitlines():
            if ':' in line:
                u, p = line.strip().split(':', 1)
                if u == username and p == password:
                    return True
        return False
    except:
        return False

# ---------- Rykten (stuffs.json) ----------
def get_all_rumors():
    data = read_github_json('stuffs.json', {"rumors": []})
    if "rumors" not in data:
        data["rumors"] = []
    # Säkerställ att varje rykte har alla fält
    for r in data["rumors"]:
        if "likes" not in r:
            r["likes"] = 0
        if "liked_by" not in r:
            r["liked_by"] = []
        if "comments" not in r:
            r["comments"] = []
        if "timestamp" not in r:
            r["timestamp"] = time.time()
    return data

def save_rumors(data):
    write_github_json('stuffs.json', data, "Update rumors")

def add_rumor(author, title, content):
    data = get_all_rumors()
    new_rumor = {
        "id": int(time.time() * 1000),  # unikt ID
        "author": author,
        "title": title,
        "content": content,
        "likes": 0,
        "liked_by": [],
        "comments": [],
        "timestamp": time.time()
    }
    data["rumors"].insert(0, new_rumor)  # nyast överst
    save_rumors(data)
    # Ge XP för att skapa rykte
    user_data = add_xp(author, 10)
    return new_rumor, user_data

def like_rumor(rumor_id, username):
    data = get_all_rumors()
    for r in data["rumors"]:
        if r["id"] == rumor_id:
            if username in r["liked_by"]:
                return False, "Redan gillat", None
            r["likes"] += 1
            r["liked_by"].append(username)
            save_rumors(data)
            # Ge XP för like (bara om man gillar någon annans)
            if r["author"] != username:
                user_data = add_xp(username, 2)
            else:
                user_data = get_users_data().get(username, {})
            return True, "Gillade!", user_data
    return False, "Rykte finns inte", None

def add_comment(rumor_id, username, comment_text):
    data = get_all_rumors()
    for r in data["rumors"]:
        if r["id"] == rumor_id:
            r["comments"].append({
                "author": username,
                "text": comment_text,
                "timestamp": time.time()
            })
            save_rumors(data)
            # Ge XP för kommentar (2 XP)
            user_data = add_xp(username, 2)
            return True, user_data
    return False, None

# ---------- Flask routes ----------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if check_login(username, password):
        # Hämta användardata
        users = get_users_data()
        if username not in users:
            users[username] = {"level": 1, "xp": 0, "coins": 50, "last_rumor_time": 0}
            save_users_data(users)
        user_info = users[username]
        return jsonify({
            "success": True,
            "username": username,
            "level": user_info.get("level", 1),
            "xp": user_info.get("xp", 0),
            "coins": user_info.get("coins", 50),
            "cooldown_seconds": get_cooldown_seconds(user_info.get("level", 1))
        })
    else:
        return jsonify({"success": False, "message": "Fel användarnamn eller lösenord"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"success": False, "message": "Krävs"}), 400
    # Lägg till i logins-filen
    try:
        result = github_request('GET', 'logins')
        if result:
            content = base64.b64decode(result['content']).decode('utf-8')
            sha = result['sha']
        else:
            content = ""
            sha = None
        if f"{username}:" in content:
            return jsonify({"success": False, "message": "Användare finns redan"}), 409
        new_content = content.rstrip() + "\n" + f"{username}:{password}" + ("\n" if not content.endswith("\n") else "")
        new_base64 = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
        payload = {"message": "New user", "content": new_base64}
        if sha:
            payload["sha"] = sha
        github_request('PUT', 'logins', payload)
        # Skapa användardata
        users = get_users_data()
        users[username] = {"level": 1, "xp": 0, "coins": 50, "last_rumor_time": 0}
        save_users_data(users)
        return jsonify({"success": True, "message": "Konto skapat"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/get_user', methods=['POST'])
def get_user():
    data = request.json
    username = data.get('username')
    users = get_users_data()
    user = users.get(username, {"level": 1, "xp": 0, "coins": 50, "last_rumor_time": 0})
    return jsonify({
        "level": user.get("level", 1),
        "xp": user.get("xp", 0),
        "coins": user.get("coins", 50),
        "cooldown_seconds": get_cooldown_seconds(user.get("level", 1)),
        "last_rumor_time": user.get("last_rumor_time", 0)
    })

@app.route('/create_rumor', methods=['POST'])
def create_rumor():
    data = request.json
    username = data.get('username')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    if not title or not content:
        return jsonify({"success": False, "message": "Titel och innehåll krävs"}), 400
    
    users = get_users_data()
    user = users.get(username, {"level": 1, "xp": 0, "coins": 50, "last_rumor_time": 0})
    last_time = user.get("last_rumor_time", 0)
    cooldown = get_cooldown_seconds(user.get("level", 1))
    now = time.time()
    if now - last_time < cooldown:
        remaining = int(cooldown - (now - last_time))
        return jsonify({"success": False, "message": f"Vänta {remaining} sekunder"}), 429
    
    rumor, updated_user = add_rumor(username, title, content)
    # Uppdatera last_rumor_time
    users[username]['last_rumor_time'] = now
    save_users_data(users)
    return jsonify({
        "success": True,
        "rumor": rumor,
        "user": {
            "level": updated_user.get("level", 1),
            "xp": updated_user.get("xp", 0),
            "coins": updated_user.get("coins", 50),
            "cooldown_seconds": get_cooldown_seconds(updated_user.get("level", 1))
        }
    })

@app.route('/like_rumor', methods=['POST'])
def like_rumor_route():
    data = request.json
    rumor_id = data.get('rumor_id')
    username = data.get('username')
    ok, msg, user_data = like_rumor(rumor_id, username)
    if ok:
        return jsonify({"success": True, "message": msg, "user": user_data})
    else:
        return jsonify({"success": False, "message": msg}), 400

@app.route('/comment_rumor', methods=['POST'])
def comment_rumor_route():
    data = request.json
    rumor_id = data.get('rumor_id')
    username = data.get('username')
    comment_text = data.get('comment', '').strip()
    if not comment_text:
        return jsonify({"success": False, "message": "Kommentar får inte vara tom"}), 400
    ok, user_data = add_comment(rumor_id, username, comment_text)
    if ok:
        # Hämta uppdaterade rykten för att skicka tillbaka
        rumors = get_all_rumors()
        return jsonify({"success": True, "user": user_data, "rumors": rumors["rumors"]})
    else:
        return jsonify({"success": False, "message": "Kunde inte kommentera"}), 400

@app.route('/get_rumors', methods=['GET'])
def get_rumors():
    data = get_all_rumors()
    return jsonify({"rumors": data["rumors"]})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
