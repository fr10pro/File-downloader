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

# Global variables for task management
tasks = {}
tasks_lock = threading.Lock()
MAX_PARALLEL_DOWNLOADS = 100

WELCOME_TEXT = """
**Welcome to File Downloader Bot!**

Send a direct link to:
- Download with speed updates
- Choose format: Video / Document
- Share file easily on Telegram

**New Features:**
- Multiple parallel downloads (up to 100)
- Set custom thumbnail with /setimage

Need help? Contact @Fr10pro
"""

def get_task_id(msg: Message):
    """Generate unique task ID using chat ID and message ID"""
    return f"{msg.chat.id}_{msg.id}"  # Fixed: msg.id instead of msg.message_id

@app.on_message(filters.command("start"))
def start(_, msg: Message):
    msg.reply_text(WELCOME_TEXT)

@app.on_message(filters.command("setimage") & filters.reply)
def set_thumbnail(_, msg: Message):
    """Handle custom thumbnail setting"""
    if not msg.reply_to_message.photo:
        return msg.reply("⚠️ Please reply to a photo with /setimage to set it as thumbnail.")
    
    try:
        # Download the largest available photo size
        photo = msg.reply_to_message.photo
        file_id = photo.file_id
        app.download_media(file_id, file_name=THUMB_PATH)
        msg.reply("✅ Thumbnail set successfully!")
    except Exception as e:
        msg.reply(f"❌ Failed to set thumbnail: {e}")

@app.on_message(filters.text & ~filters.command(["start", "setimage"]))
def handle_link(_, msg: Message):
    """Handle download requests with parallel download support"""
    url = msg.text.strip()
    if not url.startswith("http"):
        return msg.reply("❌ Invalid link. Please send a valid direct download link.")
    
    # Check parallel download limit
    with tasks_lock:
        if len(tasks) >= MAX_PARALLEL_DOWNLOADS:
            return msg.reply("⚠️ Server busy! Too many parallel downloads. Try again later.")
    
    filename = url.split("/")[-1].split("?")[0]
    task_id = get_task_id(msg)
    
    # Create task entry
    with tasks_lock:
        tasks[task_id] = {
            "filename": filename,
            "cancel_flag": False,
            "status": "downloading"
        }
    
    # Create download message with cancel button
    download_msg = msg.reply(
        f"**Downloading `{filename}`...**\n0 MB • 0 MB | 0 MB/s",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{task_id}")]
        ])
    )
    
    # Update task with download message reference
    with tasks_lock:
        tasks[task_id]["download_msg"] = download_msg
    
    # Start download thread
    threading.Thread(target=download_thread, args=(url, filename, task_id)).start()

def download_thread(url: str, filename: str, task_id: str):
    """Thread function for downloading files"""
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
                # Check for cancellation
                with tasks_lock:
                    task = tasks.get(task_id)
                    if not task or task.get("cancel_flag"):
                        update_download_msg(task_id, f"❌ **Download canceled:** `{filename}`")
                        cleanup_task(filename, task_id)
                        return
                
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time()
                    
                    # Update progress every second
                    if now - last_update >= 1:
                        speed = round((downloaded / 1024 / 1024) / (now - start_time + 0.1), 2)
                        done_mb = round(downloaded / 1024 / 1024, 2)
                        update_download_msg(
                            task_id,
                            f"**Downloading `{filename}`...**\n{done_mb} MB • {total_mb} MB | {speed} MB/s"
                        )
                        last_update = now
        
        # Update task status
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["status"] = "completed"
        
        # Show format selection
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("As Video", callback_data=f"v|{task_id}"),
                InlineKeyboardButton("As Document", callback_data=f"d|{task_id}")
            ]
        ])
        update_download_msg(
            task_id,
            f"✅ **Downloaded `{filename}` ({total_mb} MB)**\nChoose upload format:",
            buttons
        )
        
    except Exception as e:
        update_download_msg(task_id, f"❌ Error downloading: `{e}`")
        cleanup_task(filename, task_id)
    finally:
        # Don't remove task yet - wait for upload selection
        pass

def update_download_msg(task_id: str, text: str, markup=None):
    """Update download progress message safely"""
    try:
        with tasks_lock:
            task = tasks.get(task_id)
            if not task or "download_msg" not in task:
                return
            
            # Edit message if possible
            task["download_msg"].edit(text, reply_markup=markup)
    except:
        pass

def cleanup_task(filename: str, task_id: str):
    """Clean up files and task entries"""
    try:
        if os.path.exists(filename):
            os.remove(filename)
    except:
        pass
    
    with tasks_lock:
        if task_id in tasks:
            del tasks[task_id]

@app.on_callback_query()
def handle_callback(_, cb: CallbackQuery):
    """Handle all callback queries (cancel/download format)"""
    data = cb.data.split("|")
    if len(data) < 2:
        return
    
    action, task_id = data[0], data[1]
    
    if action == "cancel":
        # Handle download cancellation
        with tasks_lock:
            task = tasks.get(task_id)
            if not task:
                cb.answer("⚠️ Task already completed or canceled")
                return
            
            if task["status"] == "downloading":
                task["cancel_flag"] = True
                cb.message.edit("❌ **Download canceled by user.**")
            else:
                cb.answer("⚠️ Cannot cancel - download already completed")
        return
    
    # Handle upload format selection
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            cb.answer("⚠️ Task expired or invalid")
            return
        
        filename = task.get("filename")
        if not filename or not os.path.exists(filename):
            cb.message.edit("❌ File not found or expired.")
            cleanup_task(filename, task_id)
            return
    
    cb.message.edit("**Uploading file...**")
    
    # Use thumbnail if exists
    thumb = THUMB_PATH if os.path.exists(THUMB_PATH) else None
    start_time = time()
    caption = f"{filename} | Made by @Fr10pro"
    
    try:
        if action == "v":
            # Upload as video
            sent = cb.message.reply_video(
                video=filename,
                caption=caption,
                thumb=thumb,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )
        else:
            # Upload as document
            sent = cb.message.reply_document(
                document=filename,
                caption=caption,
                thumb=thumb,
                progress=upload_progress,
                progress_args=(cb.message, start_time)
            )
        
        # Clean up after successful upload
        cb.message.delete()
        sent.reply(f"✅ **Uploaded!**\n**Share this link:** [t.me/{app.get_me().username}](https://t.me/{app.get_me().username})")
    
    except Exception as e:
        cb.message.edit(f"❌ Upload failed: `{e}`")
    finally:
        cleanup_task(filename, task_id)

def upload_progress(current, total, message: Message, start_time):
    """Update upload progress message"""
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
    """Show downloaded files in admin panel"""
    files = [f for f in os.listdir() if os.path.isfile(f) and not f.endswith('.py')]
    
    # Get active tasks
    with tasks_lock:
        active_tasks = [
            f"{task['filename']} ({task['status']})" 
            for task in tasks.values()
        ]
    
    html = """
    <html><head><title>Admin Panel - Downloaded Files</title>
    <style>
    body { background: #0e0e0e; color: white; font-family: Arial; padding: 30px; }
    h1 { color: #00ff88; }
    ul { list-style-type: none; padding: 0; }
    li { margin-bottom: 10px; background: #1f1f1f; padding: 10px; border-radius: 8px; }
    .section { margin-top: 30px; }
    </style></head><body>
    <h1>Downloaded Files</h1>
    <ul>
    {% for file in files %}
        <li>{{ loop.index }}. {{ file }}</li>
    {% else %}
        <li>No files found.</li>
    {% endfor %}
    </ul>
    
    <div class="section">
        <h1>Active Tasks ({{ active_count }}/{{ max_tasks }})</h1>
        <ul>
        {% for task in active_tasks %}
            <li>{{ loop.index }}. {{ task }}</li>
        {% else %}
            <li>No active tasks</li>
        {% endfor %}
        </ul>
    </div>
    </body></html>
    """
    return render_template_string(
        html, 
        files=files,
        active_tasks=active_tasks,
        active_count=len(active_tasks),
        max_tasks=MAX_PARALLEL_DOWNLOADS
    )

# === Keep-Alive Web Server ===
@web.route('/')
def home():
    return "Bot is running! Visit /admin to view downloaded files."

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    app.run()
