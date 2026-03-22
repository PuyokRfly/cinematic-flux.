from flask import Flask, render_template, request, Response, jsonify
import yt_dlp
import threading
import json
import os
import subprocess
import queue
import time
import uuid
import re
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
            percent_raw = d.get('_percent_str', '0%').strip().replace('%', '')
            try:
                percent = float(percent_raw)
            except ValueError:
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
            q.put({
                'id':     dl_id,
                'status': 'finished',
                'title':  downloads[dl_id].get('title', 'Unknown'),
                'format': downloads[dl_id].get('format', 'mp4'),
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
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            with downloads_lock:
                if dl_id in downloads:
                    downloads[dl_id]['title'] = title
    except Exception:
        pass


# ─── Background Download Thread ────────────────────────────────────────────

def run_download(dl_id, url, fmt):
    hook = make_progress_hook(dl_id)

    opts = {
        'format':          'bestaudio/best' if fmt == 'mp3' else 'bestvideo+bestaudio/best',
        'outtmpl':         os.path.join(DOWNLOAD_PATH, '%(title).50s.%(ext)s'),
        'progress_hooks':  [hook],
        'quiet':           True,
        'no_warnings':     True,
        'merge_output_format': 'mp4' if fmt == 'mp4' else None,
    }

    if fmt == 'mp3':
        opts['postprocessors'] = [{
            'key':              'FFmpegExtractAudio',
            'preferredcodec':   'mp3',
            'preferredquality': '192',
        }]

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


@app.route('/vault-status')
def vault_status():
    """Return real-time disk usage of the external drive."""
    if not os.path.isdir(DOWNLOAD_PATH):
        return jsonify({'error': 'Drive not mounted'}), 200  # 200 so UI handles gracefully

    try:
        cmd = ['df', '-h', DOWNLOAD_PATH, '--output=pcent,used,avail,size']
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()
        # Skip header line, parse data line
        lines = result.strip().splitlines()
        parts = lines[-1].split()
        return jsonify({
            'percent':   parts[0].replace('%', ''),
            'used':      parts[1],
            'available': parts[2],
            'total':     parts[3],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/files', methods=['GET'])
def list_files():
    """Returns a list of all files in the USB drive sorted by newest first."""
    if not os.path.exists(DOWNLOAD_PATH):
        return jsonify([])
    
    files = []
    for f in os.listdir(DOWNLOAD_PATH):
        path = os.path.join(DOWNLOAD_PATH, f)
        if os.path.isfile(path):
            try:
                stats = os.stat(path)
                size_mb = stats.st_size / (1024 * 1024)
                files.append({
                    "name": f,
                    "size": f"{size_mb:.2f} MB",
                    "format": f.split('.')[-1].lower() if '.' in f else 'unknown',
                    "date": time.strftime('%b %d, %Y', time.localtime(stats.st_mtime)),
                    "timestamp": stats.st_mtime
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
    app.run(debug=False, port=5000, threaded=True)
