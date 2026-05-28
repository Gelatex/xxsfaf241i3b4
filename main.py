import os
import base64
import requests
from flask import Flask, request, jsonify

# Skapa Flask-appen
app = Flask(__name__)

# ---------------------------
# Hjälpfunktioner för GitHub
# ---------------------------
def get_github_file_content():
    """Hämtar innehållet i logins-filen från GitHub och returnerar (content, sha)"""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise Exception("GITHUB_TOKEN saknas i miljövariabler")
    
    url = "https://api.github.com/repos/Gelatex/xxsfaf241i3b4/contents/logins"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Kunde inte läsa logins-filen: {resp.status_code}")
    data = resp.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    return content, data['sha']

def update_github_file(content, sha):
    """Uppdaterar logins-filen på GitHub med nytt innehåll"""
    token = os.environ.get('GITHUB_TOKEN')
    url = "https://api.github.com/repos/Gelatex/xxsfaf241i3b4/contents/logins"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    new_content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    payload = {
        "message": "Uppdaterar logins-fil via Falun Rykten 2 API",
        "content": new_content_base64,
        "sha": sha
    }
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise Exception(f"Kunde inte uppdatera logins-filen: {resp.status_code}")
    return True

def check_login(username, password):
    """Kontrollerar om användarnamn och lösenord finns i logins-filen"""
    try:
        content, _ = get_github_file_content()
    except Exception as e:
        print("Fel vid inloggningskontroll:", e)
        return False
    lines = content.splitlines()
    for line in lines:
        if ':' not in line:
            continue
        u, p = line.strip().split(':', 1)
        if u == username and p == password:
            return True
    return False

def add_user(username, password):
    """Lägger till en ny användare i logins-filen"""
    try:
        content, sha = get_github_file_content()
    except Exception as e:
        return False, str(e)
    
    # Kontrollera om användaren redan finns
    lines = content.splitlines()
    for line in lines:
        if ':' in line and line.split(':', 1)[0] == username:
            return False, "Användarnamnet finns redan"
    
    # Lägg till ny rad
    new_content = content.rstrip() + "\n" + f"{username}:{password}" + ("\n" if not content.endswith("\n") else "")
    try:
        update_github_file(new_content, sha)
        return True, "Användare skapad"
    except Exception as e:
        return False, str(e)

# ---------------------------
# API-routes (endast backend)
# ---------------------------
@app.route('/')
def home():
    """Roten ger bara ett meddelande – HTML finns separat"""
    return jsonify({
        "message": "Falun Rykten 2 API är igång!",
        "endpoints": {
            "POST /login": "Logga in med {username, password}",
            "POST /register": "Registrera ny användare med {username, password}"
        }
    })

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({"success": False, "message": "Användarnamn och lösenord krävs"}), 400
    
    if check_login(username, password):
        return jsonify({"success": True, "message": "Inloggning lyckades"})
    else:
        return jsonify({"success": False, "message": "Fel användarnamn eller lösenord"}), 401

@app.route('/register', methods=['POST'])
def register():
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
    else:
        return jsonify({"success": False, "message": msg}), 409

# ---------------------------
# Starta servern
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
