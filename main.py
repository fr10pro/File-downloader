import os
from flask import Flask, request
from bot_handler import app  # Pyrogram app

web_app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_URL")  # Example: https://your-app-name.onrender.com

@web_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    app.process_update(request.get_data())
    return "ok"

@web_app.route("/", methods=["GET"])
def home():
    return "Bot is running."

if __name__ == "__main__":
    app.start()
    app.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
