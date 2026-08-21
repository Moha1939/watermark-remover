import os
import subprocess
import uuid
import json
import shutil
from flask import Flask, request, jsonify, send_from_directory, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_EXT = {"mp4", "mov", "mkv", "avi", "webm"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB cap (free hosting tiers are disk/RAM limited)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def run(cmd):
    """Run a subprocess command, raise with stderr on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return result


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "video" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["video"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Unsupported or missing file"}), 400

    job_id = uuid.uuid4().hex
    ext = file.filename.rsplit(".", 1)[1].lower()
    video_path = os.path.join(UPLOAD_DIR, f"{job_id}.{ext}")
    file.save(video_path)

    # Extract a preview frame + basic video info
    frame_path = os.path.join(UPLOAD_DIR, f"{job_id}_frame.jpg")
    try:
        run([
            "ffmpeg", "-y", "-i", video_path,
            "-vf", "select=eq(n\\,0)", "-vframes", "1", frame_path,
        ])
        probe = run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json", video_path,
        ])
        dims = json.loads(probe.stdout)["streams"][0]
    except Exception as e:
        return jsonify({"error": f"Could not process video: {e}"}), 500

    return jsonify({
        "job_id": job_id,
        "ext": ext,
        "frame_url": f"/api/frame/{job_id}",
        "width": dims["width"],
        "height": dims["height"],
    })


@app.route("/api/frame/<job_id>")
def get_frame(job_id):
    return send_from_directory(UPLOAD_DIR, f"{job_id}_frame.jpg")


@app.route("/api/process", methods=["POST"])
def process():
    data = request.get_json(force=True)
    job_id = data.get("job_id")
    ext = data.get("ext")
    x, y, w, h = data.get("x"), data.get("y"), data.get("w"), data.get("h")

    if not all(isinstance(v, (int, float)) for v in (x, y, w, h)):
        return jsonify({"error": "Invalid region"}), 400

    video_path = os.path.join(UPLOAD_DIR, f"{job_id}.{ext}")
    if not os.path.exists(video_path):
        return jsonify({"error": "Upload not found, please re-upload"}), 404

    x, y, w, h = int(x), int(y), int(max(w, 4)), int(max(h, 4))
    out_path = os.path.join(OUTPUT_DIR, f"{job_id}_clean.mp4")

    # delogo needs even width/height for some codecs; nudge if needed
    try:
        run([
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"delogo=x={x}:y={y}:w={w}:h={h}:show=0",
            "-c:a", "copy",
            out_path,
        ])
    except Exception as e:
        return jsonify({"error": f"Processing failed: {e}"}), 500

    return jsonify({"download_url": f"/api/download/{job_id}"})


@app.route("/api/download/<job_id>")
def download(job_id):
    return send_from_directory(
        OUTPUT_DIR, f"{job_id}_clean.mp4",
        as_attachment=True, download_name="watermark_removed.mp4"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
