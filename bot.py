import os
import threading
from time import time
import requests
from flask import Flask, render_template_string
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# ==== CONFIG ====
API_ID = 28593211
API_HASH = "27ad7de4fe5cab9f8e310c5cc4b8d43d"
BOT_TOKEN = "8145398845:AAH9Vid4Px1l3KrEMcTy4WUgHUCRMg4Pmas"
THUMB_PATH = "thumb.jpg"
# ================

app = Client("file_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)

cancel_flags = {}

WELCOME_TEXT = """
**Welcome to File Downloader Bot!**

Send a direct link to:
- Download with speed updates
- Choose format: Video / Document
- Share file easily on Telegram

Need help? Contact @Fr10pro
"""

@app.on_message(filters.command("start"))
def start(_, msg: Message):
    msg.reply_text(WELCOME_TEXT)

@app.on_message(filters.text & ~filters.command("start"))
def handle_link(_, msg: Message):
    url = msg.text.strip()
    if not url.startswith("http"):
        return msg.reply("Invalid link. Please send a valid direct download link.")

    filename = url.split("/")[-1].split("?")[0]
    download_msg = msg.reply(f"**Downloading `{filename}`...**\n0 MB • 0 MB | 0 MB/s",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{filename[:40]}")]
                             ]))

    cancel_flags[filename] = False

    def download_thread():
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": url
            }
            r = requests.get(url, headers=headers, stream=True, timeout=30)
            total = int(r.headers.get('content-length', 0))
            total_mb = round(total / 1024 / 1024, 2)

            with open(filename, 'wb') as f:
                downloaded = 0
                start_time = time()
                last_update = time()

                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if cancel_flags.get(filename):
                        download_msg.edit(f"❌ **Download canceled:** `{filename}`")
                        f.close()
                        os.remove(filename)
                        return

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time()
                        if now - last_update >= 1:
                            speed = round((downloaded / 1024 / 1024) / (now - start_time + 0.1), 2)
                            done_mb = round(downloaded / 1024 / 1024, 2)
                            download_msg.edit(f"**Downloading `{filename}`...**\n{done_mb} MB • {total_mb} MB | {speed} MB/s",
                                              reply_markup=InlineKeyboardMarkup([
                                                  [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{filename[:40]}")]
                                              ]))
                            last_update = now

            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("As Video", callback_data=f"v|{filename[:40]}"),
                    InlineKeyboardButton("As Document", callback_data=f"d|{filename[:40]}")
                ]
            ])
            download_msg.edit(f"✅ **Downloaded `{filename}` ({total_mb} MB)**\nChoose upload format:", reply_markup=buttons)

        except Exception as e:
            download_msg.edit(f"❌ Error downloading: `{e}`")
        finally:
            cancel_flags.pop(filename, None)

    threading.Thread(target=download_thread).start()

@app.on_callback_query()
def handle_callback(_, cb: CallbackQuery):
    if cb.data.startswith("cancel|"):
        fname_part = cb.data.split("|")[1]
        matches = [f for f in cancel_flags if f.startswith(fname_part)]
        if matches:
            cancel_flags[matches[0]] = True
            cb.message.edit("❌ **Download canceled by user.**")
        else:
            cb.message.edit("⚠️ No active download found.")
        return

    action, fname_part = cb.data.split("|")
    file_match = [f for f in os.listdir() if f.startswith(fname_part)]
    if not file_match:
        return cb.message.edit("❌ File not found or expired.")

    file_path = file_match[0]
    caption = f"{file_path} | Made by @Fr10pro"
    cb.message.edit("**Uploading file...**")

    thumb = THUMB_PATH if os.path.exists(THUMB_PATH) else None
    start_time = time()

    try:
        if action == "v":
            sent = cb.message.reply_video(
                video=file_path,
                caption=caption,
                thumb=thumb,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )
        else:
            sent = cb.message.reply_document(
                document=file_path,
                caption=caption,
                thumb=thumb,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )

        cb.message.delete()
        sent.reply(f"✅ **Uploaded!**\n**Share this link:** [t.me/{app.get_me().username}](https://t.me/{app.get_me().username})")

    except Exception as e:
        cb.message.edit(f"❌ Upload failed: `{e}`")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def upload_progress(current, total, message: Message, start_time):
    percent = current * 100 / total
    speed = round(current / 1024 / 1024 / (time() - start_time + 0.1), 2)
    done_mb = round(current / 1024 / 1024, 2)
    total_mb = round(total / 1024 / 1024, 2)
    try:
        message.edit(f"**Uploading...**\n{done_mb} MB • {total_mb} MB | {speed} MB/s")
    except:
        pass

# === Admin Panel UI ===
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

# === Keep-Alive Web Server ===
@web.route('/')
def home():
    return "Bot is running! Visit /admin to view downloaded files."

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    app.run()