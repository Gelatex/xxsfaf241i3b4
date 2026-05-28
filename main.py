import requests
import base64
import os
from flask import Flask, request, jsonify

# ... resten av din kod ...

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    # 1. Validering
    if not username or not password:
        return jsonify({"success": False, "message": "Användarnamn och lösenord krävs"}), 400

    # 2. GitHub-konfiguration
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    REPO_OWNER = "Gelatex"
    REPO_NAME = "xxsfaf241i3b4"
    FILE_PATH = "logins"

    # 3. Hämta nuvarande fil och SHA (behövs för att uppdatera)
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        get_response = requests.get(url, headers=headers)
        get_response.raise_for_status()  # Kasta fel om något går fel
        file_info = get_response.json()
        sha = file_info["sha"]
        current_content = base64.b64decode(file_info["content"]).decode('utf-8')
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": f"Kunde inte läsa logins-fil: {str(e)}"}), 500

    # 4. Kolla om användaren redan finns (gör en enkel check)
    if f"{username}:" in current_content:
        return jsonify({"success": False, "message": "Användarnamnet är upptaget"}), 409

    # 5. Skapa nytt innehåll
    new_content = current_content + f"{username}:{password}\n"
    new_content_base64 = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')

    # 6. Uppdatera filen
    update_data = {
        "message": f"Lägger till användare {username}",
        "content": new_content_base64,
        "sha": sha
    }

    try:
        put_response = requests.put(url, headers=headers, json=update_data)
        put_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": f"Kunde inte spara i GitHub: {str(e)}"}), 500

    return jsonify({"success": True, "message": f"Användare {username} skapades!"}), 201
