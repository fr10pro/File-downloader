import os
import threading
import uuid
import asyncio
from time import time
import requests
from flask import Flask, render_template_string
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from PIL import Image
from io import BytesIO

# ==== CONFIG ====
API_ID = 28593211
API_HASH = "27ad7de4fe5cab9f8e310c5cc4b8d43d"
BOT_TOKEN = "7005276207:AAG3RHlqz-KOliwGVecOv457iVF5Zs0m4pM"
THUMB_PATH = "thumb.jpg"
MAX_CONCURRENT_DOWNLOADS = 1000  # Maximum concurrent downloads
# ================

app = Client("file_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)

# Global dictionaries for state management
download_states = {}
file_info = {}
user_thumbnails = {}

# Clean up temp files on startup
for file in os.listdir():
    if file.endswith(".temp"):
        try:
            os.remove(file)
        except:
            pass

WELCOME_TEXT = """
**Welcome to File Downloader Bot!**

Send a direct link to:
- Download with speed updates
- Choose format: Video / Document
- Share file easily on Telegram

**New Features:**
- Multiple parallel downloads (up to 1000)
- Custom thumbnails (/setimage)

Need help? Contact @Fr10pro
"""

@app.on_message(filters.command("start"))
def start(_, msg: Message):
    msg.reply_text(WELCOME_TEXT)

@app.on_message(filters.command("setimage"))
async def set_thumbnail(_, msg: Message):
    if not msg.photo:
        return await msg.reply("Please send an image with /setimage command")
    
    try:
        # Get the largest available photo
        photo = msg.photo[-1]
        file_id = photo.file_id
        
        # Download and process image
        buf = BytesIO()
        await app.download_media(file_id, file_name=buf)
        buf.seek(0)
        
        img = Image.open(buf)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((320, 320))
        
        # Save thumbnail per user
        user_thumb = f"thumb_{msg.from_user.id}.jpg"
        img.save(user_thumb, "JPEG")
        user_thumbnails[msg.from_user.id] = user_thumb
        
        await msg.reply_text("✅ Thumbnail set successfully!")
    except Exception as e:
        await msg.reply_text(f"❌ Error setting thumbnail: {str(e)}")

@app.on_message(filters.text & ~filters.command(["start", "setimage"]))
def handle_link(_, msg: Message):
    url = msg.text.strip()
    if not url.startswith("http"):
        return msg.reply("Invalid link. Please send a valid direct download link.")

    if len(download_states) >= MAX_CONCURRENT_DOWNLOADS:
        return msg.reply("🚫 Server is busy. Please try again later.")

    original_filename = url.split("/")[-1].split("?")[0]
    temp_filename = f"{uuid.uuid4()}.temp"
    
    download_msg = msg.reply(f"**Downloading `{original_filename}`...**\n0 MB • 0 MB | 0 MB/s",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{msg.from_user.id}|{temp_filename}")]
                             ]))

    state_key = f"{download_msg.chat.id}:{download_msg.id}"
    download_states[state_key] = {
        'cancel': False,
        'temp_file': temp_filename,
        'original_filename': original_filename
    }

    threading.Thread(target=download_thread, args=(url, temp_filename, original_filename, download_msg)).start()

def download_thread(url, temp_filename, original_filename, download_msg):
    state_key = f"{download_msg.chat.id}:{download_msg.id}"
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
        with requests.get(url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            total_mb = round(total / (1024 * 1024), 2)

            with open(temp_filename, 'wb') as f:
                downloaded = 0
                start_time = time()
                last_update = time()

                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if state_key in download_states and download_states[state_key].get('cancel'):
                        download_msg.edit(f"❌ **Download canceled:** `{original_filename}`")
                        return
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time()
                        if now - last_update >= 1:
                            speed = round((downloaded / (1024 * 1024)) / (now - start_time + 0.1), 2)
                            done_mb = round(downloaded / (1024 * 1024), 2)
                            try:
                                download_msg.edit(
                                    f"**Downloading `{original_filename}`...**\n"
                                    f"{done_mb} MB • {total_mb} MB | {speed} MB/s",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{download_msg.from_user.id}|{temp_filename}")]
                                    ])
                                )
                            except:
                                pass
                            last_update = now

        # Store file info for upload
        file_info[temp_filename] = original_filename

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("As Video", callback_data=f"v|{temp_filename}"),
                InlineKeyboardButton("As Document", callback_data=f"d|{temp_filename}")
            ]
        ])
        download_msg.edit(f"✅ **Downloaded `{original_filename}` ({total_mb} MB)**\nChoose upload format:", reply_markup=buttons)

    except Exception as e:
        download_msg.edit(f"❌ Error downloading: `{str(e)}`")
    finally:
        if state_key in download_states:
            del download_states[state_key]

@app.on_callback_query()
def handle_callback(_, cb: CallbackQuery):
    if cb.data.startswith("cancel|"):
        _, user_id, temp_filename = cb.data.split("|", 2)
        if cb.from_user.id != int(user_id):
            return cb.answer("You didn't start this download!", show_alert=True)
        
        # Find the download state
        state_key = next((k for k, v in download_states.items() if v['temp_file'] == temp_filename), None)
        
        if state_key:
            download_states[state_key]['cancel'] = True
            cb.message.edit("❌ **Download canceled by user.**")
        else:
            cb.message.edit("⚠️ No active download found.")
        return

    action, temp_filename = cb.data.split("|", 1)
    if temp_filename not in file_info:
        return cb.message.edit("❌ File not found or expired.")

    original_filename = file_info[temp_filename]
    caption = f"{original_filename} | Made by @Fr10pro"
    cb.message.edit("**Uploading file...**")

    # Get user-specific thumbnail if available
    thumb = user_thumbnails.get(cb.from_user.id, THUMB_PATH) if os.path.exists(user_thumbnails.get(cb.from_user.id, THUMB_PATH)) else None
    start_time = time()

    try:
        if action == "v":
            sent = cb.message.reply_video(
                video=temp_filename,
                caption=caption,
                thumb=thumb,
                file_name=original_filename,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )
        else:
            sent = cb.message.reply_document(
                document=temp_filename,
                caption=caption,
                thumb=thumb,
                file_name=original_filename,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )

        cb.message.delete()
        sent.reply(f"✅ **Uploaded!**\n**Share this link:** [t.me/{app.get_me().username}](https://t.me/{app.get_me().username})")

    except Exception as e:
        cb.message.edit(f"❌ Upload failed: `{str(e)}`")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        if temp_filename in file_info:
            del file_info[temp_filename]

def upload_progress(current, total, message: Message, start_time):
    percent = current * 100 / total
    speed = round(current / (1024 * 1024) / (time() - start_time + 0.1), 2)
    done_mb = round(current / (1024 * 1024), 2)
    total_mb = round(total / (1024 * 1024), 2)
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
    .stats { margin-top: 20px; padding: 15px; background: #1f1f1f; border-radius: 8px; }
    </style></head><body>
    <h1>Downloaded Files</h1>
    <div class="stats">
        <strong>Active Downloads:</strong> {{ active_downloads }}<br>
        <strong>Pending Uploads:</strong> {{ pending_uploads }}
    </div>
    <ul>
    {% for file in files %}
        <li>{{ loop.index }}. {{ file }}</li>
    {% else %}
        <li>No files found.</li>
    {% endfor %}
    </ul></body></html>
    """
    return render_template_string(html, files=files, 
                                active_downloads=len(download_states),
                                pending_uploads=len(file_info))

# === Keep-Alive Web Server ===
@web.route('/')
def home():
    return "Bot is running! Visit /admin to view downloaded files."

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    app.run()
