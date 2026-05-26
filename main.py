import discord
import json
import os
from discord.ext import tasks

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

CHANNEL_ID = 1508923142138232953
DATA_FILE = "approved_rykten.json"

# Ladda eller skapa datafil
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        approved_posts = json.load(f)
else:
    approved_posts = []
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(approved_posts, f, ensure_ascii=False, indent=2)

@client.event
async def on_ready():
    print(f"Bot är online som {client.user}")
    check_reactions.start()

@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author.bot:
        return
    
    # Lägg till reaktioner på nya rykten
    await message.add_reaction("✅")  # Ja
    await message.add_reaction("❌")  # Nej

@tasks.loop(minutes=5)  # Kollar var 5:e minut
async def check_reactions():
    global approved_posts
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        return

    async for message in channel.history(limit=50):
        if message.author.bot:
            continue

        ja_count = 0
        nej_count = 0

        for reaction in message.reactions:
            if str(reaction.emoji) == "✅":
                ja_count = reaction.count - 1  # subtrahera botens egen reaktion
            elif str(reaction.emoji) == "❌":
                nej_count = reaction.count - 1

        if ja_count > nej_count and ja_count >= 2:  # Minst 2 ja-röster
            # Kolla om redan godkänd
            if not any(p["discord_id"] == message.id for p in approved_posts):
                post = {
                    "discord_id": message.id,
                    "title": message.content.split("\n")[0].replace("**Titel:**", "").strip(),
                    "author": "Anonym",
                    "content": "\n".join(message.content.split("\n")[2:]).strip(),
                    "date": message.created_at.strftime("%Y-%m-%d"),
                    "likes": 0
                }
                approved_posts.append(post)
                
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(approved_posts, f, ensure_ascii=False, indent=2)

client.run("MTUwODkyMzMxMTI2OTA4NTQ0Nw.GSV2jb.uOCjor2M5up-2TXXdYQ78iqhSowH6HduxzvAp4")