from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3

# 1. SKAPA FLASK-APPEN FÖRST (det här var felet!)
app = Flask(__name__, static_url_path='', static_folder='.')

# 2. ALLA @app.route DEKORATÖRER KOMMER EFTER APPEN ÄR SKAPAD

# En route för att visa din HTML-fil när man går till roten
@app.route('/')
def home():
    # Skickar tillbaka din index.html-fil
    return send_from_directory('.', 'index.html')

# Din befintliga login-logik
@app.route('/login', methods=['POST'])
def login():
    # ... din kod här ...
    return jsonify({"success": True, "message": "Inloggad!"})

# Din nya register-logik som sparar på GitHub (se till att requests är importerad)
@app.route('/register', methods=['POST'])
def register():
    # ... din kod här ...
    return jsonify({"success": True, "message": "Konto skapat!"})

# 3. STARTA SERVERN (detta är standard, ändra inte)
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
