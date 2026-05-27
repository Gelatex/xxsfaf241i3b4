from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

DATA_FILE = "rykten.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        posts = json.load(f)
else:
    posts = []
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

@app.route('/')
def home():
    return "Falunrykten API är uppe!"

@app.route('/posts', methods=['GET'])
def get_posts():
    # Sortera: VIP först, sedan nyast
    sorted_posts = sorted(posts, key=lambda x: (x.get("vip", False), x.get("date")), reverse=True)
    return jsonify(sorted_posts)

@app.route('/posts', methods=['POST'])
def add_post():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("content"):
        return jsonify({"error": "Titel och innehåll krävs"}), 400
    
    username = data.get("username", "Anonym")
    is_anonymous = data.get("anonymous", False)
    is_vip = data.get("vip", False) and username == "Ebbe"  # Endast Ebbe kan göra VIP

    new_post = {
        "title": data["title"],
        "author": "Anonym" if is_anonymous else username,
        "content": data["content"],
        "date": "2026-05-26",
        "likes": 0,
        "vip": is_vip,
        "images": data.get("images", [])  # Lista med bild-URL:er
    }
    
    posts.append(new_post)
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    
    return jsonify({"message": "Ryktet publicerat!"})

@app.route('/posts/<int:index>', methods=['DELETE'])
def delete_post(index):
    username = request.args.get("username")
    if username != "Ebbe":
        return jsonify({"error": "Endast admin kan ta bort"}), 403
    if 0 <= index < len(posts):
        deleted = posts.pop(index)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
        return jsonify({"message": "Borttaget"})
    return jsonify({"error": "Hittades inte"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
