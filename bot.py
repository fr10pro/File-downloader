import os
import threading
from time import time
import requests
import yt_dlp
from flask import Flask, render_template_string
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# ==== CONFIG ====
API_ID = 28593211
API_HASH = "27ad7de4fe5cab9f8e310c5cc4b8d43d"
BOT_TOKEN = "7654681113:AAFBAvdHIhIGl9XCO9_poX0Qy8xV6a5qKIo"
THUMB_PATH = "thumb.jpg"
# ================

app = Client("file_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)

cancel_flags = {}

WELCOME_TEXT = """
**Welcome to the Stream & File Downloader Bot!**

Send any direct or streaming link:
- YouTube / Pornhub / HLS / MP4 / etc.
- Watch real-time progress
- Choose format: Video / Document

Bot by @Fr10pro
"""

@app.on_message(filters.command("start"))
def start(_, msg: Message):
    msg.reply_text(WELCOME_TEXT)

@app.on_message(filters.text & ~filters.command("start"))
def handle_link(_, msg: Message):
    url = msg.text.strip()
    if not url.startswith("http"):
        return msg.reply("Invalid link. Please send a valid streaming or direct URL.")

    filename = f"{int(time())}.mp4"
    download_msg = msg.reply(f"**Downloading...**\n0 MB • 0 MB | 0 MB/s",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{filename}")]
                             ]))

    cancel_flags[filename] = False

    def update_progress(d, message, filename):
        if d.get('status') == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            percent = downloaded / total * 100 if total else 0
            speed = d.get('speed', 0) / 1024 / 1024 if d.get('speed') else 0
            done_mb = round(downloaded / 1024 / 1024, 2)
            total_mb = round(total / 1024 / 1024, 2) if total else 0
            try:
                message.edit(f"**Downloading...**\n{done_mb} MB • {total_mb} MB | {speed:.2f} MB/s",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{filename}")]
                             ]))
            except: pass

    def download_thread():
        try:
            ydl_opts = {
                'outtmpl': filename,
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': True,
                'no_call_home': True,
                'progress_hooks': [lambda d: update_progress(d, download_msg, filename)],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if cancel_flags.get(filename):
                download_msg.edit(f"❌ **Download canceled:** `{filename}`")
                if os.path.exists(filename):
                    os.remove(filename)
                return

            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("As Video", callback_data=f"v|{filename}"),
                    InlineKeyboardButton("As Document", callback_data=f"d|{filename}")
                ]
            ])
            file_size = round(os.path.getsize(filename) / 1024 / 1024, 2)
            download_msg.edit(f"✅ **Downloaded `{filename}` ({file_size} MB)**\nChoose upload format:", reply_markup=buttons)

        except Exception as e:
            download_msg.edit(f"❌ Error downloading: `{e}`")
        finally:
            cancel_flags.pop(filename, None)

    threading.Thread(target=download_thread).start()

@app.on_callback_query()
def handle_callback(_, cb: CallbackQuery):
    if cb.data.startswith("cancel|"):
        fname = cb.data.split("|")[1]
        cancel_flags[fname] = True
        cb.message.edit("❌ **Download canceled by user.**")
        return

    action, fname = cb.data.split("|")
    if not os.path.exists(fname):
        return cb.message.edit("❌ File not found or expired.")

    caption = f"{fname} | Made by @Fr10pro"
    cb.message.edit("**Uploading file...**")

    thumb = THUMB_PATH if os.path.exists(THUMB_PATH) else None
    start_time = time()

    try:
        if action == "v":
            sent = cb.message.reply_video(
                video=fname,
                caption=caption,
                thumb=thumb,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )
        else:
            sent = cb.message.reply_document(
                document=fname,
                caption=caption,
                thumb=thumb,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )

        cb.message.delete()
        sent.reply(f"✅ **Uploaded!**\n**Share this bot:** [t.me/{app.get_me().username}](https://t.me/{app.get_me().username})")

    except Exception as e:
        cb.message.edit(f"❌ Upload failed: `{e}`")
    finally:
        if os.path.exists(fname):
            os.remove(fname)

def upload_progress(current, total, message: Message, start_time):
    percent = current * 100 / total
    speed = round(current / 1024 / 1024 / (time() - start_time + 0.1), 2)
    done_mb = round(current / 1024 / 1024, 2)
    total_mb = round(total / 1024 / 1024, 2)
    try:
        message.edit(f"**Uploading...**\n{done_mb} MB • {total_mb} MB | {speed} MB/s")
    except:
        pass

# === Web Admin Panel ===
@web.route('/admin')
def admin_panel():
    files = [f for f in os.listdir() if os.path.isfile(f) and not f.endswith('.py')]
    html = """
    <html><head><title>Admin Panel - Downloaded Files</title>
    <style>
    body { background: #0e0e0e; color: white; font-family: Arial; padding: 30px; }
    h1 { color: #00ff88; }
    ul { list-style-type: none; padding: 0; }
    li { margin-bottom: 10px; background: #1f1f1f; padding: 10px; border-radius: 8px; }
    </style></head><body>
    <h1>Downloaded Files</h1>
    <ul>
    {% for file in files %}
        <li>{{ loop.index }}. {{ file }}</li>
    {% else %}
        <li>No files found.</li>
    {% endfor %}
    </ul></body></html>
    """
    return render_template_string(html, files=files)

@web.route('/')
def home():
    return "Bot is running! Visit /admin to view downloaded files."

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    app.run()
