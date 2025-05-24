# bot.py
import os
import asyncio
import logging
from flask import Flask, request
from pyrogram import Client, filters
from pyrogram.types import Message
from werkzeug.middleware.proxy_fix import ProxyFix
from threading import Thread
from time import time
import requests

# --- CONFIGURATION ---
API_ID = 28593211
API_HASH = "27ad7de4fe5cab9f8e310c5cc4b8d43d"
BOT_TOKEN = "7696316358:AAGZw4OUGAT628QX2DBleIVV2JWQTfiQu88"
ADMIN_ID = 5559075560
BASE_WEBHOOK_URL = "https://file-downloader-zufi.onrender.com"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# --- FLASK APP ---
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

# --- PYROGRAM CLIENT ---
app_bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=10,
)

# --- BACKGROUND FLASK SERVER ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    asyncio.run(app_bot.process_updates([update]))
    return "ok", 200

@app.route("/", methods=["GET"])
def root():
    return "<h1>Telegram Downloader Bot is Live!</h1>"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- BOT HANDLERS ---
@app_bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text(
        "Welcome to the Downloader Bot!\n\n"
        "Send me a direct download link or supported URL and I’ll fetch it for you."
    )

@app_bot.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message: Message):
    await message.reply_text("Admin panel is under development.")

@app_bot.on_message(filters.text & filters.private)
async def handle_links(client, message: Message):
    url = message.text.strip()
    msg = await message.reply("Processing your link...")

    try:
        file = requests.get(url, stream=True)
        filename = url.split("/")[-1].split("?")[0]
        start = time()

        with open(filename, "wb") as f:
            for chunk in file.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        elapsed = round(time() - start, 2)
        await msg.edit(f"Downloaded in {elapsed} sec. Uploading...")

        await message.reply_document(filename, caption=f"Uploaded: `{filename}`")
        os.remove(filename)
        await msg.delete()

    except Exception as e:
        await msg.edit(f"Failed: {e}")

# --- MAIN ENTRY POINT ---
async def main():
    await app_bot.start()
    await app_bot.set_webhook(f"{BASE_WEBHOOK_URL}/{BOT_TOKEN}")
    Thread(target=run_flask).start()
    logger.info("Bot is up and running with webhook...")

if __name__ == "__main__":
    asyncio.run(main())
