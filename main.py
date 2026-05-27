from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATA_FILE = "rykten.json"

# Ladda eller skapa databas
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        posts = json.load(f)
else:
    posts = []
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

def save_posts():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

@app.route('/')
def home():
    return "🔥 Falunrykten API – backend online"

@app.route('/posts', methods=['GET'])
def get_posts():
    # Sortera: VIP först, sedan nyast (antar att datum finns)
    sorted_posts = sorted(posts, key=lambda x: (not x.get("vip", False), x.get("date", "")), reverse=False)
    # VIP ska vara överst => VIP True först
    sorted_posts = sorted(posts, key=lambda x: (0 if x.get("vip") else 1, x.get("date", "")))
    return jsonify(sorted_posts)

@app.route('/posts', methods=['POST'])
def add_post():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("content"):
        return jsonify({"error": "Titel och innehåll krävs"}), 400
    
    username = data.get("username", "Anonym")
    is_anonymous = data.get("anonymous", False)
    is_vip = data.get("vip", False) and username == "Ebbe"
    images = data.get("images", [])  # lista med base64 eller url:er

    new_post = {
        "title": data["title"],
        "author": "Anonym" if is_anonymous else username,
        "anonymous": is_anonymous,
        "content": data["content"],
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "likes": 0,
        "liked_by": [],
        "vip": is_vip,
        "images": images,
        "comments": []
    }
    posts.append(new_post)
    save_posts()
    return jsonify({"message": "Ryktet publicerat!"})

@app.route('/posts/<int:index>/like', methods=['POST'])
def like_post(index):
    if 0 <= index < len(posts):
        data = request.get_json()
        username = data.get("username")
        if not username:
            return jsonify({"error": "Ange användarnamn"}), 400
        if username in posts[index].get("liked_by", []):
            return jsonify({"message": "Redan gillat"}), 200
        posts[index]["likes"] = posts[index].get("likes", 0) + 1
        posts[index].setdefault("liked_by", []).append(username)
        save_posts()
        return jsonify({"likes": posts[index]["likes"]})
    return jsonify({"error": "Inlägg finns inte"}), 404

@app.route('/posts/<int:index>/comment', methods=['POST'])
def add_comment(index):
    if 0 <= index < len(posts):
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
        posts[index].setdefault("comments", []).append(comment)
        save_posts()
        return jsonify({"message": "Kommentar tillagd"})
    return jsonify({"error": "Inlägg saknas"}), 404

@app.route('/posts/<int:index>', methods=['DELETE'])
def delete_post(index):
    username = request.headers.get("X-User")
    if username != "Ebbe":
        return jsonify({"error": "Endast admin (Ebbe) kan radera"}), 403
    if 0 <= index < len(posts):
        deleted = posts.pop(index)
        save_posts()
        return jsonify({"message": "Ryktet raderat"})
    return jsonify({"error": "Inlägg ej funnet"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
