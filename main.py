from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime
import uuid

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
    # Sortera efter VIP först, sedan datum (nyast överst)
    sorted_posts = sorted(posts, key=lambda x: (0 if x.get("vip") else 1, x.get("date", "")), reverse=False)
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
        "id": uuid.uuid4().hex,  # unikt ID
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
    return jsonify({"message": "Ryktet publicerat!", "id": new_post["id"]})

@app.route('/posts/<post_id>/like', methods=['POST'])
def like_post(post_id):
    for post in posts:
        if post["id"] == post_id:
            data = request.get_json()
            username = data.get("username")
            if not username:
                return jsonify({"error": "Ange användarnamn"}), 400
            if username in post.get("liked_by", []):
                return jsonify({"message": "Redan gillat"}), 200
            post["likes"] = post.get("likes", 0) + 1
            post.setdefault("liked_by", []).append(username)
            save_posts()
            return jsonify({"likes": post["likes"]})
    return jsonify({"error": "Inlägg finns inte"}), 404

@app.route('/posts/<post_id>/comment', methods=['POST'])
def add_comment(post_id):
    for post in posts:
        if post["id"] == post_id:
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
            post.setdefault("comments", []).append(comment)
            save_posts()
            return jsonify({"message": "Kommentar tillagd"})
    return jsonify({"error": "Inlägg saknas"}), 404

@app.route('/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    username = request.headers.get("X-User")
    if username != "Ebbe":
        return jsonify({"error": "Endast admin (Ebbe) kan radera"}), 403
    for i, post in enumerate(posts):
        if post["id"] == post_id:
            posts.pop(i)
            save_posts()
            return jsonify({"message": "Ryktet raderat"})
    return jsonify({"error": "Inlägg ej funnet"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
