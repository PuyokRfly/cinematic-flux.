from flask import Flask, render_template, request, Response, jsonify, send_from_directory
import yt_dlp
import threading
import json
import os
import subprocess
import queue
import time
import uuid
import re
import shutil
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='.')

# Fallback to local 'downloads' folder if not set
DOWNLOAD_PATH = os.environ.get('FLUX_DOWNLOAD_PATH', './downloads')
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# Global registry: download_id -> {"queue": Queue, "title": str, "status": str}
downloads = {}
downloads_lock = threading.Lock()


# ─── yt-dlp Progress Hook ───────────────────────────────────────────────────

def make_progress_hook(dl_id):
    """Returns a progress_hook closure bound to a specific download ID."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    def hook(d):
        with downloads_lock:
            if dl_id not in downloads:
                return
            q = downloads[dl_id]['queue']

        if d['status'] == 'downloading':
            p_str = d.get('_percent_str')
            if p_str:
                p_clean = ansi_escape.sub('', p_str).strip().replace('%', '')
                try:
                    percent = float(p_clean)
                except ValueError:
                    percent = 0.0
            else:
                downloaded = d.get('downloaded_bytes')
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                if downloaded is not None and total:
                    percent = round((downloaded / total) * 100, 1)
                else:
                    percent = 0.0
                
            def clean_str(k):
                val = d.get(k) or ''
                return ansi_escape.sub('', val).strip() or 'N/A'

            payload = {
                'id':         dl_id,
                'status':     'downloading',
                'percent':    percent,
                'speed':      clean_str('_speed_str'),
                'eta':        clean_str('_eta_str'),
                'downloaded': clean_str('_downloaded_bytes_str'),
                'total':      clean_str('_total_bytes_str') if d.get('_total_bytes_str') else clean_str('_total_bytes_estimate_str'),
                'title':      downloads[dl_id].get('title', 'Unknown'),
                'format':     downloads[dl_id].get('format', 'mp4'),
            }
            q.put(payload)

        elif d['status'] == 'finished':
            with downloads_lock:
                downloads[dl_id]['status'] = 'finished'
            
            # Resolve safe filename
            raw_path = d.get('info_dict', {}).get('_filename') or d.get('filename')
            final_filename = os.path.basename(raw_path) if raw_path else "Unknown"
            
            q.put({
                'id':     dl_id,
                'status': 'finished',
                'title':  downloads[dl_id].get('title', 'Unknown'),
                'format': downloads[dl_id].get('format', 'mp4'),
                'filename': final_filename
            })

        elif d['status'] == 'error':
            with downloads_lock:
                downloads[dl_id]['status'] = 'error'
            q.put({
                'id':     dl_id,
                'status': 'error',
                'message': 'yt-dlp encountered an error.',
            })

    return hook


# ─── Info Extractor (runs before download to grab title) ───────────────────

def extract_info(url, dl_id):
    """Extract video title without downloading."""
    ydl_opts = {
        'quiet': True, 
        'skip_download': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            with downloads_lock:
                if dl_id in downloads:
                    downloads[dl_id]['title'] = title
                    downloads[dl_id]['thumbnail'] = info.get('thumbnail')
    except Exception:
        pass


# ─── Background Download Thread ────────────────────────────────────────────

def run_download(dl_id, url, fmt):
    hook = make_progress_hook(dl_id)

    opts = {
        'format':          'bestaudio/best' if fmt == 'mp3' else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl':         os.path.join(DOWNLOAD_PATH, '%(title)s.%(ext)s'),
        'progress_hooks':  [make_progress_hook(dl_id)],
        'quiet':           True,
        'no_warnings':     True,
        'nocheckcertificate': True,
        'ignoreerrors':    False,
        'logtostderr':     False,
        'writethumbnail':  True,
        'user_agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    }
    
    opts['postprocessors'] = []

    if fmt == 'mp3':
        opts['postprocessors'].append({
            'key':              'FFmpegExtractAudio',
            'preferredcodec':   'mp3',
            'preferredquality': '320', # Ultra quality for Car Audio
        })

    # Always attempt to convert thumbnail to jpg
    opts['postprocessors'].append({
        'key': 'FFmpegThumbnailsConvertor',
        'format': 'jpg',
    })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        # Force disk sync to ensure data is written to the USB drive
        os.sync()
    except Exception as e:
        q = downloads[dl_id]['queue']
        q.put({'id': dl_id, 'status': 'error', 'message': str(e)})
        with downloads_lock:
            downloads[dl_id]['status'] = 'error'


# ─── Routes ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('code.html')


@app.route('/download', methods=['POST'])
def start_download():
    data = request.get_json(force=True)
    url  = data.get('url', '').strip()
    fmt  = data.get('format', 'mp3').lower()   # 'mp3' | 'mp4'

    if not url:
        return jsonify({'error': 'URL kosong. Tempel URL YouTube terlebih dahulu.'}), 400

    # USB mount check
    if not os.path.isdir(DOWNLOAD_PATH):
        return jsonify({'error': f"Flashdisk tidak ditemukan di: {DOWNLOAD_PATH}"}), 400

    # Create download record
    dl_id = str(uuid.uuid4())[:8]
    with downloads_lock:
        downloads[dl_id] = {
            'queue':  queue.Queue(),
            'title':  'Fetching info…',
            'format': fmt,
            'status': 'starting',
        }

    # Fetch title in background then start download
    def bootstrap():
        extract_info(url, dl_id)
        run_download(dl_id, url, fmt)

    threading.Thread(target=bootstrap, daemon=True).start()

    return jsonify({'status': 'started', 'id': dl_id})


@app.route('/progress/<dl_id>')
def progress(dl_id):
    """Server-Sent Events stream for a specific download ID."""
    with downloads_lock:
        if dl_id not in downloads:
            return jsonify({'error': 'Download ID tidak ditemukan.'}), 404
        q = downloads[dl_id]['queue']

    def generate():
        while True:
            try:
                item = q.get(timeout=30)   # 30-second timeout = heartbeat window
                yield f"data: {json.dumps(item)}\n\n"
                if item.get('status') in ('finished', 'error'):
                    break
            except queue.Empty:
                # Heartbeat comment so browser doesn't drop the connection
                yield ": heartbeat\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':  'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering if behind proxy
        }
    )
@app.route('/stream/<path:filename>')
def stream_media(filename):
    """Streams video/audio files with support for HTTP Range requests."""
    safe_name = os.path.basename(filename)
    return send_from_directory(DOWNLOAD_PATH, safe_name)

@app.route('/thumbnail/<path:filename>')
def get_thumbnail(filename):
    """Serves the thumbnail associated with a media file."""
    safe_name = os.path.basename(filename)
    base = os.path.splitext(safe_name)[0]
    
    # Try common thumbnail extensions
    for ext in ['.jpg', '.png', '.webp', '.jpeg']:
        thumb_path = os.path.join(DOWNLOAD_PATH, base + ext)
        if os.path.exists(thumb_path):
            return send_from_directory(DOWNLOAD_PATH, base + ext)
            
    return jsonify({"error": "Thumbnail not found"}), 404



@app.route('/vault-status')
def vault_status():
    """Return real-time disk usage of the external drive."""
    if not os.path.exists(DOWNLOAD_PATH):
        return jsonify({"error": "Path not found"}), 404
        
    try:
        total, used, free = shutil.disk_usage(DOWNLOAD_PATH)
        percent = (used / total) * 100 if total > 0 else 0
        return jsonify({
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "percent_used": float(round(percent, 1))
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/config', methods=['GET', 'POST'])
def handle_config():
    global DOWNLOAD_PATH
    if request.method == 'POST':
        data = request.get_json(force=True)
        new_path = data.get('download_path', '').strip()
        if not new_path:
            return jsonify({"error": "Path tidak boleh kosong"}), 400
        
        # Verify/Create path
        try:
            os.makedirs(new_path, exist_ok=True)
            DOWNLOAD_PATH = new_path
            
            # Persist to .env
            env_path = os.path.join(os.path.dirname(__file__), '.env')
            env_lines = []
            found = False
            
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.startswith('FLUX_DOWNLOAD_PATH='):
                            env_lines.append(f"FLUX_DOWNLOAD_PATH={new_path}\n")
                            found = True
                        else:
                            env_lines.append(line)
            
            if not found:
                env_lines.append(f"FLUX_DOWNLOAD_PATH={new_path}\n")
                
            with open(env_path, 'w') as f:
                f.writelines(env_lines)

            return jsonify({"status": "success", "download_path": os.path.abspath(DOWNLOAD_PATH)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({
        "download_path": os.path.abspath(DOWNLOAD_PATH)
    })

@app.route('/files', methods=['GET'])
def list_files():
    """Returns a list of all files in the USB drive sorted by newest first."""
    if not os.path.exists(DOWNLOAD_PATH):
        return jsonify([])
    
    files = []
    for f in os.listdir(DOWNLOAD_PATH):
        # Only list media files, ignore thumbnails and parts
        if f.endswith(('.jpg', '.png', '.webp', '.jpeg', '.part', '.ytdl')):
            continue
            
        path = os.path.join(DOWNLOAD_PATH, f)
        if os.path.isfile(path):
            try:
                stats = os.stat(path)
                size_mb = stats.st_size / (1024 * 1024)
                base = os.path.splitext(f)[0]
                
                # Check for associated thumbnail
                has_thumb = False
                for ext in ['.jpg', '.png', '.webp', '.jpeg']:
                    if os.path.exists(os.path.join(DOWNLOAD_PATH, base + ext)):
                        has_thumb = True
                        break

                files.append({
                    "name": f,
                    "size": f"{size_mb:.2f} MB",
                    "format": f.split('.')[-1].lower() if '.' in f else 'unknown',
                    "date": time.strftime('%b %d, %Y', time.localtime(stats.st_mtime)),
                    "timestamp": stats.st_mtime,
                    "has_thumbnail": has_thumb
                })
            except Exception:
                pass
    
    # Sort by timestamp, newest first
    files.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(files)


@app.route('/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Securely deletes a file from the USB and performs a disk sync."""
    if not os.path.exists(DOWNLOAD_PATH):
        return jsonify({"error": "Drive disconnected"}), 400

    # Prevent path traversal
    safe_name = os.path.basename(filename)
    target = os.path.join(DOWNLOAD_PATH, safe_name)
    
    if os.path.exists(target):
        try:
            os.remove(target)
            os.sync()  # Force OS cache to flush to USB physical sectors
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "File not found"}), 404


# ─── Entry Point ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n🎬 Cinematic Flux server starting on http://localhost:5000")
    print(f"   Output path: {DOWNLOAD_PATH}\n")
    app.run(debug=True, port=5000, threaded=True)
