import os
import asyncio
import logging
from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.types import Message
from yt_dlp import YoutubeDL
import time
import threading

# Logging
logging.basicConfig(level=logging.INFO)

# Configs
API_ID = 28593211                     # Replace with your API ID
API_HASH = "27ad7de4fe5cab9f8e310c5cc4b8d43d"            # Replace with your API HASH
BOT_TOKEN = "7696316358:AAGZw4OUGAT628QX2DBleIVV2JWQTfiQu88"          # Replace with your BOT TOKEN
BASE_WEBHOOK_URL = "https://file-downloader-zufi.onrender.com"  # Render domain
PORT = int(os.environ.get("PORT", 5000))

# Pyrogram Client
app_bot = Client("downloader-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Flask App
web = Flask(__name__)

# Download options
ydl_opts = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'noplaylist': True,
    'quiet': True,
    'merge_output_format': 'mp4',
}

# Create downloads folder
os.makedirs("downloads", exist_ok=True)

# Download function
def download_media(url):
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info.get("title", "No Title")

# Telegram Command
@app_bot.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    await message.reply_text("Send me a video/link to download from YouTube, TikTok, Instagram, etc.")

@app_bot.on_message(filters.text & filters.private)
async def handle_download(client, message: Message):
    url = message.text.strip()
    msg = await message.reply("Downloading...")
    try:
        filename, title = await asyncio.to_thread(download_media, url)
        await msg.edit("Uploading...")
        await message.reply_video(video=filename, caption=title)
        os.remove(filename)
        await msg.delete()
    except Exception as e:
        await msg.edit(f"Failed: {e}")

# Webhook route
@web.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json()
    asyncio.create_task(app_bot.process_update(update))
    return jsonify(ok=True)

# Health check
@web.route("/")
def home():
    return "Bot is alive!"

# Run Flask with asyncio wrapper
async def run_web():
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{PORT}"]
    await serve(web, config)

# Main runner
async def main():
    await app_bot.set_webhook(f"{BASE_WEBHOOK_URL}/{BOT_TOKEN}")
    await asyncio.gather(app_bot.start(), run_web())

# Start
if __name__ == "__main__":
    asyncio.run(main())
