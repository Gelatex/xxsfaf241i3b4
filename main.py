import os
import base64
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Tillåter alla domäner att prata med APIet

# ---------------------------
# Hjälpfunktioner för GitHub
# ---------------------------
def get_github_file_content():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise Exception("GITHUB_TOKEN saknas")
    url = "https://api.github.com/repos/Gelatex/xxsfaf241i3b4/contents/logins"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Kunde inte läsa logins-filen: {resp.status_code}")
    data = resp.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    return content, data['sha']

def update_github_file(content, sha):
    token = os.environ.get('GITHUB_TOKEN')
    url = "https://api.github.com/repos/Gelatex/xxsfaf241i3b4/contents/logins"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    new_content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    payload = {"message": "Uppdaterar logins", "content": new_content_base64, "sha": sha}
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise Exception(f"Kunde inte uppdatera: {resp.status_code}")
    return True

def check_login(username, password):
    try:
        content, _ = get_github_file_content()
    except Exception:
        return False
    for line in content.splitlines():
        if ':' in line:
            u, p = line.strip().split(':', 1)
            if u == username and p == password:
                return True
    return False

def add_user(username, password):
    try:
        content, sha = get_github_file_content()
    except Exception as e:
        return False, str(e)
    for line in content.splitlines():
        if ':' in line and line.split(':', 1)[0] == username:
            return False, "Användarnamnet finns redan"
    new_content = content.rstrip() + "\n" + f"{username}:{password}" + ("\n" if not content.endswith("\n") else "")
    try:
        update_github_file(new_content, sha)
        return True, "Användare skapad"
    except Exception as e:
        return False, str(e)

# ---------------------------
# API-vägar
# ---------------------------
@app.route('/')
def home():
    return jsonify({"message": "Falun Rykten 2 API är igång!", "endpoints": {"POST /login": "logga in", "POST /register": "registrera"}})

@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"success": False, "message": "Användarnamn och lösenord krävs"}), 400
    if check_login(username, password):
        return jsonify({"success": True, "message": "Inloggning lyckades"})
    return jsonify({"success": False, "message": "Fel användarnamn eller lösenord"}), 401

@app.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"success": False, "message": "Användarnamn och lösenord krävs"}), 400
    if len(username) < 3:
        return jsonify({"success": False, "message": "Användarnamn måste vara minst 3 tecken"}), 400
    if len(password) < 4:
        return jsonify({"success": False, "message": "Lösenord måste vara minst 4 tecken"}), 400
    ok, msg = add_user(username, password)
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 409

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
