import os
import threading
import uuid
import asyncio
from time import time
import requests
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from PIL import Image
import shutil

# ==== CONFIG ====
API_ID = 28593211
API_HASH = "27ad7de4fe5cab9f8e310c5cc4b8d43d"
BOT_TOKEN = "7005276207:AAG3RHlqz-KOliwGVecOv457iVF5Zs0m4pM"
THUMB_PATH = "thumb.jpg"
MAX_CONCURRENT_DOWNLOADS = 1000  # Maximum concurrent downloads
# ================

# Ensure directories exist
os.makedirs("thumbnails", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

app = Client("file_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)

# Global dictionaries for state management
download_states = {}
file_info = {}
user_thumbnails = {}
lock = threading.Lock()

# Clean up temp files on startup
for file in os.listdir("downloads"):
    if file.endswith(".temp"):
        try:
            os.remove(os.path.join("downloads", file))
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
        # Download the photo directly to a file
        temp_file = f"temp_{msg.from_user.id}.jpg"
        temp_path = os.path.join("downloads", temp_file)
        await msg.download(file_name=temp_path)
        
        # Process image
        img = Image.open(temp_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((320, 320))
        
        # Save thumbnail per user
        user_thumb = f"thumb_{msg.from_user.id}.jpg"
        thumb_path = os.path.join("thumbnails", user_thumb)
        img.save(thumb_path, "JPEG")
        
        with lock:
            user_thumbnails[msg.from_user.id] = thumb_path
        
        await msg.reply_text("✅ Thumbnail set successfully!")
    except Exception as e:
        await msg.reply_text(f"❌ Error setting thumbnail: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.on_message(filters.text & ~filters.command(["start", "setimage"]))
def handle_link(_, msg: Message):
    url = msg.text.strip()
    if not url.startswith("http"):
        return msg.reply("Invalid link. Please send a valid direct download link.")

    with lock:
        if len(download_states) >= MAX_CONCURRENT_DOWNLOADS:
            return msg.reply("🚫 Server is busy. Please try again later.")

    original_filename = url.split("/")[-1].split("?")[0]
    temp_filename = f"{uuid.uuid4()}.temp"
    temp_path = os.path.join("downloads", temp_filename)
    
    download_msg = msg.reply(f"**Downloading `{original_filename}`...**\n0 MB • 0 MB | 0 MB/s",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{msg.from_user.id}|{temp_filename}")]
                             ]))

    state_key = f"{download_msg.chat.id}:{download_msg.id}"
    with lock:
        download_states[state_key] = {
            'cancel': False,
            'temp_file': temp_path,
            'original_filename': original_filename,
            'user_id': msg.from_user.id
        }

    threading.Thread(target=download_thread, args=(url, temp_path, original_filename, download_msg, state_key)).start()

def download_thread(url, temp_path, original_filename, download_msg, state_key):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
        with requests.get(url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            total_mb = round(total / (1024 * 1024), 2)

            with open(temp_path, 'wb') as f:
                downloaded = 0
                start_time = time()
                last_update = time()

                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    with lock:
                        state = download_states.get(state_key)
                        if not state or state.get('cancel'):
                            download_msg.edit(f"❌ **Download canceled:** `{original_filename}`")
                            return
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time()
                        if now - last_update >= 1:
                            mb_downloaded = downloaded / (1024 * 1024)
                            time_elapsed = now - start_time + 0.1
                            speed = round(mb_downloaded / time_elapsed, 2)
                            done_mb = round(mb_downloaded, 2)
                            try:
                                download_msg.edit(
                                    f"**Downloading `{original_filename}`...**\n"
                                    f"{done_mb} MB • {total_mb} MB | {speed} MB/s",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{state['user_id']}|{os.path.basename(state['temp_file'])}")]
                                    ])
                                )
                            except:
                                pass
                            last_update = now

        # Store file info for upload
        with lock:
            file_info[temp_path] = {
                'original_filename': original_filename,
                'temp_filename': os.path.basename(temp_path)
            }

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("As Video", callback_data=f"v|{os.path.basename(temp_path)}"),
                InlineKeyboardButton("As Document", callback_data=f"d|{os.path.basename(temp_path)}")
            ]
        ])
        download_msg.edit(f"✅ **Downloaded `{original_filename}` ({total_mb} MB)**\nChoose upload format:", reply_markup=buttons)

    except Exception as e:
        download_msg.edit(f"❌ Error downloading: `{str(e)}`")
    finally:
        with lock:
            if state_key in download_states:
                del download_states[state_key]

@app.on_callback_query()
def handle_callback(_, cb: CallbackQuery):
    if cb.data.startswith("cancel|"):
        _, user_id, temp_filename = cb.data.split("|", 2)
        if cb.from_user.id != int(user_id):
            return cb.answer("You didn't start this download!", show_alert=True)
        
        # Find and cancel the download
        canceled = False
        with lock:
            for state_key, state in list(download_states.items()):
                if os.path.basename(state['temp_file']) == temp_filename and state['user_id'] == int(user_id):
                    state['cancel'] = True
                    canceled = True
                    break
        
        if canceled:
            cb.message.edit("❌ **Download canceled by user.**")
        else:
            cb.message.edit("⚠️ No active download found.")
        return

    action, temp_filename = cb.data.split("|", 1)
    temp_path = os.path.join("downloads", temp_filename)
    
    if not os.path.exists(temp_path) or temp_path not in file_info:
        return cb.message.edit("❌ File not found or expired.")

    file_data = file_info[temp_path]
    original_filename = file_data['original_filename']
    caption = f"{original_filename} | Made by @Fr10pro"
    cb.message.edit("**Uploading file...**")

    # Get user-specific thumbnail if available
    thumb_path = None
    user_thumb = user_thumbnails.get(cb.from_user.id)
    if user_thumb and os.path.exists(user_thumb):
        thumb_path = user_thumb
    elif os.path.exists(THUMB_PATH):
        thumb_path = THUMB_PATH

    start_time = time()

    try:
        if action == "v":
            sent = cb.message.reply_video(
                video=temp_path,
                caption=caption,
                thumb=thumb_path,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )
        else:
            sent = cb.message.reply_document(
                document=temp_path,
                caption=caption,
                thumb=thumb_path,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )

        cb.message.delete()
        sent.reply(f"✅ **Uploaded!**\n**Share this link:** [t.me/{app.get_me().username}](https://t.me/{app.get_me().username})")

    except Exception as e:
        cb.message.edit(f"❌ Upload failed: `{str(e)}`")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        with lock:
            if temp_path in file_info:
                del file_info[temp_path]

def upload_progress(current, total, message: Message, start_time):
    speed = round(current / (1024 * 1024) / (time() - start_time + 0.1), 2)
    done_mb = round(current / (1024 * 1024), 2)
    total_mb = round(total / (1024 * 1024), 2)
    try:
        message.edit(f"**Uploading...**\n{done_mb} MB • {total_mb} MB | {speed} MB/s")
    except:
        pass

# === Enhanced Admin Panel ===
@web.route('/admin')
def admin_panel():
    # Precompute file sizes to avoid template syntax issues
    files = []
    for f in os.listdir("downloads"):
        if os.path.isfile(os.path.join("downloads", f)):
            size_bytes = os.path.getsize(os.path.join("downloads", f))
            size_mb = round(size_bytes / (1024 * 1024), 2)
            files.append({"name": f, "size": size_mb})
    
    thumbs = [f for f in os.listdir("thumbnails") if f.endswith('.jpg')]
    
    html = """
    <html><head><title>Admin Panel - File Downloader</title>
    <style>
    body { background: #0e0e0e; color: white; font-family: Arial; padding: 30px; }
    h1, h2 { color: #00ff88; }
    .container { display: flex; gap: 30px; }
    .column { flex: 1; }
    ul { list-style-type: none; padding: 0; }
    li { margin-bottom: 10px; background: #1f1f1f; padding: 10px; border-radius: 8px; }
    .stats { margin-bottom: 20px; padding: 15px; background: #1f1f1f; border-radius: 8px; }
    .thumb-item { display: flex; align-items: center; gap: 10px; }
    .thumb-img { max-width: 100px; max-height: 100px; border-radius: 5px; }
    form { margin-top: 15px; }
    button { background: #00ff88; color: #000; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; }
    button:hover { background: #00cc66; }
    </style></head><body>
    <h1>File Downloader Admin Panel</h1>
    
    <div class="stats">
        <strong>Active Downloads:</strong> {{ active_downloads }}<br>
        <strong>Pending Uploads:</strong> {{ pending_uploads }}<br>
        <strong>User Thumbnails:</strong> {{ user_thumbs }}
    </div>
    
    <div class="container">
        <div class="column">
            <h2>Downloaded Files</h2>
            <ul>
            {% for file in files %}
                <li>{{ loop.index }}. {{ file.name }} ({{ file.size }} MB)</li>
            {% else %}
                <li>No files found.</li>
            {% endfor %}
            </ul>
        </div>
        
        <div class="column">
            <h2>User Thumbnails</h2>
            <ul>
            {% for thumb in thumbs %}
                <li class="thumb-item">
                    <img src="/thumb/{{ thumb }}" class="thumb-img">
                    <span>{{ thumb }}</span>
                    <form action="/delete_thumb/{{ thumb }}" method="post">
                        <button type="submit">Delete</button>
                    </form>
                </li>
            {% else %}
                <li>No thumbnails found.</li>
            {% endfor %}
            </ul>
            
            <h2>Set Default Thumbnail</h2>
            <form action="/set_default_thumb" method="post" enctype="multipart/form-data">
                <input type="file" name="thumbnail" accept="image/*" required>
                <button type="submit">Set Default</button>
            </form>
        </div>
    </div>
    </body></html>
    """
    
    with lock:
        active = len(download_states)
        pending = len(file_info)
        thumbs_count = len(user_thumbnails)
    
    return render_template_string(html, files=files, thumbs=thumbs,
                                active_downloads=active,
                                pending_uploads=pending,
                                user_thumbs=thumbs_count)

@web.route('/thumb/<filename>')
def serve_thumbnail(filename):
    return send_from_directory("thumbnails", filename)

@web.route('/delete_thumb/<filename>', methods=['POST'])
def delete_thumbnail(filename):
    try:
        thumb_path = os.path.join("thumbnails", filename)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
            
            # Remove from user_thumbnails if present
            user_id = filename.replace("thumb_", "").replace(".jpg", "")
            if user_id.isdigit():
                user_id = int(user_id)
                with lock:
                    if user_id in user_thumbnails:
                        del user_thumbnails[user_id]
            
            return redirect(url_for('admin_panel'))
        else:
            return "Thumbnail not found", 404
    except Exception as e:
        return str(e), 500

@web.route('/set_default_thumb', methods=['POST'])
def set_default_thumbnail():
    if 'thumbnail' not in request.files:
        return "No file uploaded", 400
        
    file = request.files['thumbnail']
    if file.filename == '':
        return "No selected file", 400
        
    try:
        # Save to thumbnails directory
        temp_path = os.path.join("thumbnails", "temp_thumb.jpg")
        file.save(temp_path)
        
        # Process image
        img = Image.open(temp_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((320, 320))
        img.save(THUMB_PATH, "JPEG")
        
        return redirect(url_for('admin_panel'))
    except Exception as e:
        return str(e), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# === Keep-Alive Web Server ===
@web.route('/')
def home():
    return "Bot is running! Visit /admin to view downloaded files."

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    app.run()
