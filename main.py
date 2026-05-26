import discord
import json
import os
import base64
from discord.ext import tasks
from flask import Flask, jsonify
import threading

app = Flask(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

CHANNEL_ID = 1508923142138232953
DATA_FILE = "approved_rykten.json"

# === OBFUSKERAD TOKEN ===
obfuscated_token = "TVRrd09EazJNemMxVElqMllUQTBOREU0TnpRd0d5RXFZdi53cnNCWFNkbjBkd21wWnZHSFlLbUxa cXlQa1lzYUh3UVZ6bVZlYw=="

def decrypt_token(obf):
    decoded = base64.b64decode(obf.replace(" ", "")).decode('utf-8')
    key = "falunrykten1337x"
    decrypted = ""
    for i, char in enumerate(decoded):
        decrypted += chr(ord(char) ^ ord(key[i % len(key)]))
    return decrypted

TOKEN = decrypt_token(obfuscated_token)

# Ladda poster
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        approved_posts = json.load(f)
else:
    approved_posts = []
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(approved_posts, f, ensure_ascii=False, indent=2)

# === DISCORD BOT ===
@client.event
async def on_ready():
    print(f"✅ Bot online som {client.user}")
    check_reactions.start()

@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author.bot:
        return
    await message.add_reaction("✅")
    await message.add_reaction("❌")

@tasks.loop(minutes=5)
async def check_reactions():
    global approved_posts
    channel = client.get_channel(CHANNEL_ID)
    if not channel: return

    async for message in channel.history(limit=100):
        if message.author.bot: continue

        ja = 0
        nej = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == "✅":
                ja = reaction.count - 1
            elif str(reaction.emoji) == "❌":
                nej = reaction.count - 1

        if ja > nej and ja >= 2:
            if not any(p.get("discord_id") == message.id for p in approved_posts):
                post = {
                    "discord_id": message.id,
                    "title": message.content.split("\n")[0].replace("**Titel:**", "").strip(),
                    "author": "Anonym",
                    "content": "\n".join(message.content.split("\n")[2:]).strip() if len(message.content.split("\n")) > 1 else message.content,
                    "date": message.created_at.strftime("%Y-%m-%d"),
                    "likes": 0
                }
                approved_posts.append(post)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(approved_posts, f, ensure_ascii=False, indent=2)

# === FLASK ROUTES (för hemsidan) ===
@app.route('/posts')
def get_posts():
    return jsonify(approved_posts)

@app.route('/')
def home():
    return "Falunrykten Bot & API is running!"

# Starta botten i separat tråd
def run_bot():
    client.run(TOKEN)

if __name__ == "__main__":
    # Starta botten i bakgrunden
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Starta Flask (Render använder port 10000)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
