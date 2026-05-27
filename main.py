from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

# Hämta databas-URL från Render (sätts automatiskt när du lägger till PostgreSQL)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            anonymous BOOLEAN DEFAULT FALSE,
            content TEXT NOT NULL,
            date TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            liked_by TEXT[] DEFAULT '{}',
            vip BOOLEAN DEFAULT FALSE,
            images TEXT[] DEFAULT '{}',
            comments JSONB DEFAULT '[]'
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/')
def home():
    return "🔥 Falunrykten API – backend online med PostgreSQL"

@app.route('/posts', methods=['GET'])
def get_posts():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM posts ORDER BY vip DESC, date DESC')
    posts = cur.fetchall()
    cur.close()
    conn.close()
    # Hantera None-värden
    for post in posts:
        if post.get('liked_by') is None:
            post['liked_by'] = []
        if post.get('images') is None:
            post['images'] = []
        if post.get('comments') is None:
            post['comments'] = []
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
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO posts (id, title, author, anonymous, content, date, likes, liked_by, vip, images, comments)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (post_id, data["title"], "Anonym" if is_anonymous else username, is_anonymous, data["content"], date_str, 0, [], is_vip, images, []))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Ryktet publicerat!", "id": post_id})

@app.route('/posts/<post_id>/like', methods=['POST'])
def like_post(post_id):
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Ange användarnamn"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT liked_by FROM posts WHERE id = %s', (post_id,))
    post = cur.fetchone()
    if not post:
        cur.close()
        conn.close()
        return jsonify({"error": "Inlägg finns inte"}), 404
    
    liked_by = post['liked_by'] or []
    if username in liked_by:
        cur.close()
        conn.close()
        return jsonify({"message": "Redan gillat"}), 200
    
    liked_by.append(username)
    cur.execute('UPDATE posts SET likes = likes + 1, liked_by = %s WHERE id = %s', (liked_by, post_id))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"likes": "ok"})

@app.route('/posts/<post_id>/comment', methods=['POST'])
def add_comment(post_id):
    data = request.get_json()
    username = data.get("username")
    text = data.get("text")
    if not username or not text:
        return jsonify({"error": "Användarnamn och kommentar krävs"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT comments FROM posts WHERE id = %s', (post_id,))
    post = cur.fetchone()
    if not post:
        cur.close()
        conn.close()
        return jsonify({"error": "Inlägg saknas"}), 404
    
    comments = post['comments'] or []
    comment = {
        "username": username,
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    comments.append(comment)
    cur.execute('UPDATE posts SET comments = %s WHERE id = %s', (comments, post_id))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Kommentar tillagd"})

@app.route('/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    username = request.headers.get("X-User")
    if username != "Ebbe":
        return jsonify({"error": "Endast admin (Ebbe) kan radera"}), 403
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM posts WHERE id = %s', (post_id,))
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        return jsonify({"error": "Inlägg ej funnet"}), 404
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Ryktet raderat"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
