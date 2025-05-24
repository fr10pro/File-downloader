bot.py

import os import asyncio from pyrogram import Client, filters from flask import Flask, request import threading import requests

============ CONFIGURATION ============

BOT_TOKEN = "7696316358:AAGZw4OUGAT628QX2DBleIVV2JWQTfiQu88" API_ID = 28593211 API_HASH = "27ad7de4fe5cab9f8e310c5cc4b8d43d" ADMIN_ID = 5559075560 BASE_WEBHOOK_URL = "https://file-downloader-zufi.onrender.com"

============ PYROGRAM BOT ============

app_bot = Client( "bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH, in_memory=True )

@app_bot.on_message(filters.command("start")) async def start_command(client, message): await message.reply("Hello! I am alive and running on Render.com.")

============ FLASK WEB SERVER ============

flask_app = Flask(name)

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"]) def webhook(): update = request.get_json(force=True) if update: app_bot.process_update(update) return "ok"

@flask_app.route("/") def index(): return "Telegram Bot Running Successfully on Render!"

============ RUN FUNCTIONS ============

async def main(): await app_bot.start() try: webhook_url = f"{BASE_WEBHOOK_URL}/{BOT_TOKEN}" await app_bot.set_webhook(webhook_url) except Exception as e: print("Webhook error:", e) print("Bot started with webhook.")

# Run Flask app in thread
threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()

if name == "main": asyncio.run(main())

