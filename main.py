from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
import uuid
import json

app = Flask(__name__)
CORS(app)

DATABASE = 'rykten.db'

def init_db():
    """Skapa tabell om den inte finns"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id TEXT PRIMARY KEY,
                  title TEXT,
                  author TEXT,
                  anonymous INTEGER,
                  content TEXT,
                  date TEXT,
                  likes INTEGER,
                  liked_by TEXT,
                  vip INTEGER,
                  images TEXT,
                  comments TEXT)''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Initiera databasen (skapar filen om den saknas)
init_db()

@app.route('/')
def home():
    return "🔥 Falunrykten API – backend online (SQLite)"

@app.route('/posts', methods=['GET'])
def get_posts():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM posts")
    rows = c.fetchall()
    posts = []
    for row in rows:
        post = dict(row)
        post['anonymous'] = bool(post['anonymous'])
        post['vip'] = bool(post['vip'])
        post['liked_by'] = json.loads(post['liked_by']) if post['liked_by'] else []
        post['images'] = json.loads(post['images']) if post['images'] else []
        post['comments'] = json.loads(post['comments']) if post['comments'] else []
        posts.append(post)
    conn.close()
    # Sortera: VIP först, sedan datum nyast
    posts.sort(key=lambda x: (0 if x['vip'] else 1, x['date']), reverse=False)
    return jsonify(posts)

@app.route('/posts', methods=['POST'])
def add_post():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("content"):
        return jsonify({"error": "Titel och innehåll krävs"}), 400
    
    username = data.get("username", "Anonym")
    is_anonymous = data.get("anonymous", False)
    is_vip = data.get("vip", False) and username == "Ebbe"
    images = data.get("images", [])
    
    post_id = uuid.uuid4().hex
    new_post = {
        "id": post_id,
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
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO posts 
                 (id, title, author, anonymous, content, date, likes, liked_by, vip, images, comments)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (post_id, new_post['title'], new_post['author'], int(new_post['anonymous']),
               new_post['content'], new_post['date'], new_post['likes'],
               json.dumps(new_post['liked_by']), int(new_post['vip']),
               json.dumps(new_post['images']), json.dumps(new_post['comments'])))
    conn.commit()
    conn.close()
    return jsonify({"message": "Ryktet publicerat!", "id": post_id})

@app.route('/posts/<post_id>/like', methods=['POST'])
def like_post(post_id):
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Ange användarnamn"}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT likes, liked_by FROM posts WHERE id = ?", (post_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Inlägg finns inte"}), 404
    
    liked_by = json.loads(row[1]) if row[1] else []
    if username in liked_by:
        conn.close()
        return jsonify({"message": "Redan gillat"}), 200
    
    new_likes = row[0] + 1
    liked_by.append(username)
    c.execute("UPDATE posts SET likes = ?, liked_by = ? WHERE id = ?",
              (new_likes, json.dumps(liked_by), post_id))
    conn.commit()
    conn.close()
    return jsonify({"likes": new_likes})

@app.route('/posts/<post_id>/comment', methods=['POST'])
def add_comment(post_id):
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
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT comments FROM posts WHERE id = ?", (post_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Inlägg finns inte"}), 404
    
    comments = json.loads(row[0]) if row[0] else []
    comments.append(comment)
    c.execute("UPDATE posts SET comments = ? WHERE id = ?", (json.dumps(comments), post_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Kommentar tillagd"})

@app.route('/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    username = request.headers.get("X-User")
    if username != "Ebbe":
        return jsonify({"error": "Endast admin (Ebbe) kan radera"}), 403
    
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    if c.rowcount == 0:
        conn.close()
        return jsonify({"error": "Inlägg ej funnet"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Ryktet raderat"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
