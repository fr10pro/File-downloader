from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import os
from werkzeug.utils import secure_filename
import mimetypes
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this for production

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {
    'video': ['mp4', 'mkv', 'webm', 'mov', 'avi'],
    'audio': ['mp3', 'wav', 'ogg', 'm4a'],
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
    'document': ['pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx', 'xls', 'xlsx'],
    'subtitle': ['vtt', 'srt'],
    'archive': ['zip', 'rar', '7z']
}
TELEGRAM_BOT_TOKEN = '7696316358:AAGZw4OUGAT628QX2DBleIVV2JWQTfiQu88'
TELEGRAM_CHAT_ID = '5559075560'

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in [
        ext for extensions in ALLOWED_EXTENSIONS.values() for ext in extensions
    ]

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type
    return 'other'

def human_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

def send_telegram_notification(action, filename, file_type=None, size=None, watch_url=None, download_url=None):
    ip = get_client_ip()
    base_url = f"http://{ip}:5000"
    
    if action == 'upload':
        message = (
            f"📥 <b>File Uploaded</b>\n\n"
            f"<b>Name:</b> {filename}\n"
            f"<b>Size:</b> {human_readable_size(size)}\n"
            f"<b>Type:</b> {file_type}\n"
            f"<b>Watch:</b> <a href=\"{base_url}{watch_url}\">Watch Now</a>\n"
            f"<b>Download:</b> <a href=\"{base_url}{download_url}\">Download</a>\n\n"
            f"<code>IP: {ip}</code>"
        )
    elif action == 'download':
        message = (
            f"📤 <b>File Downloaded</b>\n\n"
            f"<b>Name:</b> {filename}\n"
            f"<b>Size:</b> {human_readable_size(size)}\n"
            f"<b>Type:</b> {file_type}\n"
            f"<b>Link:</b> <a href=\"{base_url}{download_url}\">Download</a>\n\n"
            f"<code>IP: {ip}</code>"
        )
    elif action == 'delete':
        message = (
            f"🗑️ <b>File Deleted</b>\n\n"
            f"<b>Name:</b> {filename}\n"
            f"<b>Type:</b> {file_type}\n\n"
            f"<code>IP: {ip}</code>"
        )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    
    try:
        requests.post(url, params=params)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

@app.route('/')
def index():
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            file_type = get_file_type(filename)
            mime_type, _ = mimetypes.guess_type(filename)
            
            files.append({
                'name': filename,
                'size': human_readable_size(size),
                'type': file_type,
                'mime': mime_type or 'application/octet-stream',
                'watch_url': url_for('watch', filename=filename),
                'download_url': url_for('download_file', filename=filename),
                'date': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M')
            })
    
    # Sort by date (newest first)
    files.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        flash('No files selected')
        return redirect(url_for('index'))
    
    uploaded_files = request.files.getlist('files')
    for file in uploaded_files:
        if file.filename == '':
            continue
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            size = os.path.getsize(filepath)
            file_type = mimetypes.guess_type(filename)[0] or get_file_type(filename)
            
            send_telegram_notification(
                action='upload',
                filename=filename,
                file_type=file_type,
                size=size,
                watch_url=url_for('watch', filename=filename),
                download_url=url_for('download_file', filename=filename)
            )
        else:
            flash(f'File type not allowed: {file.filename}')
    
    return redirect(url_for('index'))

@app.route('/watch/<filename>')
def watch(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if not os.path.isfile(filepath):
        return "File not found", 404
    
    file_type = get_file_type(filename)
    mime_type, _ = mimetypes.guess_type(filename)
    
    # Check for subtitles
    subtitle_files = []
    if file_type == 'video':
        base_name = os.path.splitext(filename)[0]
        for ext in ALLOWED_EXTENSIONS['subtitle']:
            sub_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}.{ext}")
            if os.path.isfile(sub_path):
                subtitle_files.append({
                    'url': url_for('download_file', filename=f"{base_name}.{ext}"),
                    'type': ext,
                    'label': ext.upper()
                })
    
    return render_template('watch.html', 
                         filename=filename,
                         file_type=file_type,
                         mime_type=mime_type,
                         download_url=url_for('download_file', filename=filename),
                         subtitle_files=subtitle_files)

@app.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if not os.path.isfile(filepath):
        return "File not found", 404
    
    size = os.path.getsize(filepath)
    file_type = mimetypes.guess_type(filename)[0] or get_file_type(filename)
    
    send_telegram_notification(
        action='download',
        filename=filename,
        file_type=file_type,
        size=size,
        download_url=url_for('download_file', filename=filename)
    )
    
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True
    )

@app.route('/delete/<filename>')
def delete_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if not os.path.isfile(filepath):
        return "File not found", 404
    
    file_type = mimetypes.guess_type(filename)[0] or get_file_type(filename)
    
    try:
        os.remove(filepath)
        send_telegram_notification(
            action='delete',
            filename=filename,
            file_type=file_type
        )
        flash(f'Deleted: {filename}')
    except Exception as e:
        flash(f'Error deleting file: {e}')
    
    return redirect(url_for('index'))

# HTML Templates
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

app.jinja_env.globals.update(
    static=static_files,
    url_for=url_for
)

# Embedded templates
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

os.makedirs('templates', exist_ok=True)
with open('templates/index.html', 'w') as f:
    f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Local Media Host</title>
    <style>
        :root {
            --primary: #4361ee;
            --secondary: #3f37c9;
            --dark: #1f2937;
            --light: #f9fafb;
            --danger: #ef4444;
            --success: #10b981;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        body {
            background-color: var(--light);
            color: var(--dark);
            line-height: 1.6;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 1px solid #e5e7eb;
        }
        h1 {
            color: var(--primary);
        }
        .upload-area {
            background: white;
            border: 2px dashed #ccc;
            border-radius: 8px;
            padding: 30px;
            text-align: center;
            margin-bottom: 30px;
            transition: all 0.3s;
        }
        .upload-area:hover {
            border-color: var(--primary);
        }
        .upload-area.highlight {
            border-color: var(--primary);
            background-color: rgba(67, 97, 238, 0.05);
        }
        .upload-form {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .file-input {
            display: none;
        }
        .upload-btn {
            background-color: var(--primary);
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin-bottom: 15px;
            transition: background-color 0.3s;
        }
        .upload-btn:hover {
            background-color: var(--secondary);
        }
        .file-list {
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .file-item {
            display: flex;
            align-items: center;
            padding: 15px 20px;
            border-bottom: 1px solid #e5e7eb;
            transition: background-color 0.2s;
        }
        .file-item:last-child {
            border-bottom: none;
        }
        .file-item:hover {
            background-color: #f8fafc;
        }
        .file-icon {
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            color: var(--primary);
            font-size: 20px;
        }
        .file-info {
            flex: 1;
        }
        .file-name {
            font-weight: 600;
            margin-bottom: 5px;
            word-break: break-all;
        }
        .file-meta {
            display: flex;
            font-size: 14px;
            color: #6b7280;
        }
        .file-meta span {
            margin-right: 15px;
        }
        .file-actions {
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 8px 12px;
            border-radius: 5px;
            font-size: 14px;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .btn-watch {
            background-color: var(--primary);
            color: white;
        }
        .btn-watch:hover {
            background-color: var(--secondary);
        }
        .btn-download {
            background-color: var(--success);
            color: white;
        }
        .btn-download:hover {
            opacity: 0.9;
        }
        .btn-copy {
            background-color: #e0e7ff;
            color: var(--primary);
        }
        .btn-copy:hover {
            background-color: #d0d9ff;
        }
        .btn-delete {
            background-color: #fee2e2;
            color: var(--danger);
        }
        .btn-delete:hover {
            background-color: #fecaca;
        }
        .flash-messages {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }
        .flash {
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            color: white;
            animation: slideIn 0.3s, fadeOut 0.5s 3s forwards;
        }
        .flash.success {
            background-color: var(--success);
        }
        .flash.error {
            background-color: var(--danger);
        }
        @keyframes slideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
        }
        @keyframes fadeOut {
            to { opacity: 0; }
        }
        @media (max-width: 768px) {
            .file-item {
                flex-direction: column;
                align-items: flex-start;
            }
            .file-actions {
                margin-top: 10px;
                width: 100%;
                justify-content: flex-end;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Local Media Host</h1>
        </header>

        {% with messages = get_flashed_messages(with_categories=true) %}
            <div class="flash-messages">
                {% for category, message in messages %}
                    <div class="flash {{ category }}">{{ message }}</div>
                {% endfor %}
            </div>
        {% endwith %}

        <div class="upload-area" id="uploadArea">
            <form class="upload-form" id="uploadForm" action="{{ url_for('upload_files') }}" method="post" enctype="multipart/form-data">
                <input type="file" name="files" id="fileInput" class="file-input" multiple required>
                <label for="fileInput" class="upload-btn">Choose Files</label>
                <p id="fileNames">No files selected</p>
                <button type="submit" class="upload-btn">Upload Files</button>
            </form>
        </div>

        <div class="file-list">
            {% for file in files %}
                <div class="file-item">
                    <div class="file-icon">
                        {% if file.type == 'video' %}
                            📹
                        {% elif file.type == 'audio' %}
                            🎵
                        {% elif file.type == 'image' %}
                            🖼️
                        {% elif file.type == 'document' %}
                            📄
                        {% elif file.type == 'subtitle' %}
                            📝
                        {% else %}
                            📁
                        {% endif %}
                    </div>
                    <div class="file-info">
                        <div class="file-name">{{ file.name }}</div>
                        <div class="file-meta">
                            <span>{{ file.size }}</span>
                            <span>{{ file.type|upper }}</span>
                            <span>{{ file.date }}</span>
                        </div>
                    </div>
                    <div class="file-actions">
                        {% if file.type in ['video', 'audio'] %}
                            <a href="{{ file.watch_url }}" class="btn btn-watch">Watch</a>
                        {% endif %}
                        <a href="{{ file.download_url }}" class="btn btn-download">Download</a>
                        <button onclick="copyToClipboard('{{ file.download_url }}')" class="btn btn-copy">Copy Link</button>
                        <button onclick="confirmDelete('{{ file.name }}')" class="btn btn-delete">Delete</button>
                    </div>
                </div>
            {% else %}
                <div style="padding: 30px; text-align: center; color: #6b7280;">
                    No files uploaded yet.
                </div>
            {% endfor %}
        </div>
    </div>

    <script>
        // File input display
        const fileInput = document.getElementById('fileInput');
        const fileNames = document.getElementById('fileNames');
        const uploadArea = document.getElementById('uploadArea');
        
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                if (this.files.length === 1) {
                    fileNames.textContent = this.files[0].name;
                } else {
                    fileNames.textContent = `${this.files.length} files selected`;
                }
            } else {
                fileNames.textContent = 'No files selected';
            }
        });
        
        // Drag and drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            uploadArea.classList.add('highlight');
        }
        
        function unhighlight() {
            uploadArea.classList.remove('highlight');
        }
        
        uploadArea.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            fileInput.files = dt.files;
            fileInput.dispatchEvent(new Event('change'));
        }
        
        // Copy link
        function copyToClipboard(text) {
            navigator.clipboard.writeText(window.location.origin + text)
                .then(() => {
                    alert('Link copied to clipboard!');
                })
                .catch(err => {
                    console.error('Failed to copy: ', err);
                });
        }
        
        // Delete confirmation
        function confirmDelete(filename) {
            if (confirm(`Are you sure you want to delete "${filename}"?`)) {
                window.location.href = `/delete/${encodeURIComponent(filename)}`;
            }
        }
    </script>
</body>
</html>
''')

with open('templates/watch.html', 'w') as f:
    f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watch {{ filename }}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/mediaelement@4.2.16/build/mediaelementplayer.min.css">
    <style>
        :root {
            --primary: #4361ee;
            --dark: #1f2937;
            --light: #f9fafb;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        body {
            background-color: var(--dark);
            color: white;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        h1 {
            color: white;
            font-size: 1.5rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 70%;
        }
        .back-btn {
            background-color: var(--primary);
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 5px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }
        .media-container {
            width: 100%;
            max-width: 1000px;
            margin: 0 auto;
            background-color: black;
            border-radius: 8px;
            overflow: hidden;
        }
        .mejs__container {
            width: 100% !important;
            height: auto !important;
            padding-top: 56.25%; /* 16:9 aspect ratio */
        }
        .mejs__overlay {
            width: 100% !important;
            height: 100% !important;
        }
        video, .mejs__video {
            width: 100% !important;
            height: 100% !important;
            position: absolute;
            top: 0;
            left: 0;
        }
        .download-btn {
            display: inline-block;
            background-color: #10b981;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            text-decoration: none;
            margin-top: 20px;
            text-align: center;
        }
        .download-btn:hover {
            opacity: 0.9;
        }
        @media (max-width: 768px) {
            h1 {
                font-size: 1.2rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{{ filename }}</h1>
            <a href="{{ url_for('index') }}" class="back-btn">← Back to Files</a>
        </header>

        <div class="media-container">
            {% if file_type in ['video', 'audio'] %}
                <video id="player" width="100%" controls>
                    <source src="{{ url_for('download_file', filename=filename) }}" type="{{ mime_type }}">
                    {% for sub in subtitle_files %}
                        <track kind="subtitles" src="{{ sub.url }}" srclang="en" label="{{ sub.label }}">
                    {% endfor %}
                    Your browser does not support the video tag.
                </video>
            {% else %}
                <p>This file type cannot be played directly.</p>
            {% endif %}
        </div>

        <center>
            <a href="{{ download_url }}" class="download-btn">Download File</a>
        </center>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/mediaelement@4.2.16/build/mediaelement-and-player.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            new MediaElementPlayer('player', {
                features: ['playpause', 'current', 'progress', 'duration', 'volume', 'speed', 'pip', 'fullscreen'],
                speed: ['2.00', '1.75', '1.50', '1.25', '1.00', '0.75', '0.50'],
                speedChar: 'x',
                pipText: 'Picture-in-Picture',
                startLanguage: 'en',
                stretching: 'responsive'
            });
        });
    </script>
</body>
</html>
''')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)