from flask import Flask, jsonify, request
import json
import os

app = Flask(__name__)

DATA_FILE = "rykten.json"

# Ladda eller skapa fil
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
    return jsonify(posts)

@app.route('/posts', methods=['POST'])
def add_post():
    data = request.json
    if not data or not data.get("title") or not data.get("content"):
        return jsonify({"error": "Titel och innehåll krävs"}), 400
    
    new_post = {
        "title": data["title"],
        "author": data.get("author", "Anonym"),
        "content": data["content"],
        "date": "2026-05-" + str(len(posts) + 15).zfill(2),  # enkel datumhantering
        "likes": 0
    }
    
    posts.append(new_post)
    
    # Spara till fil
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    
    return jsonify({"message": "Ryktet publicerat!"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
