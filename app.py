from pathlib import Path
from datetime import datetime
from io import BytesIO
import secrets
import socket

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    jsonify,
    session,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
import qrcode

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

# New random session key and PIN every time the server starts.
app.secret_key = secrets.token_hex(32)
ACCESS_PIN = f"{secrets.randbelow(1_000_000):06d}"

# Max total size of a single upload request: 4 GB.
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024

PORT = 5000


def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def format_size(size):
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


def make_unique_path(folder: Path, filename: str) -> Path:
    candidate = folder / filename

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1

    while True:
        candidate = folder / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def get_file_type(name):
    suffix = Path(name).suffix.lower()

    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp"}:
        return "image"
    if suffix in {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}:
        return "video"
    if suffix in {".mp3", ".wav", ".m4a", ".aac", ".flac"}:
        return "audio"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        return "archive"
    if suffix in {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"}:
        return "document"
    return "file"


def get_file_list():
    files = []

    for path in UPLOAD_FOLDER.iterdir():
        if path.is_file():
            stat = path.stat()
            files.append({
                "name": path.name,
                "size": stat.st_size,
                "size_text": format_size(stat.st_size),
                "modified": stat.st_mtime,
                "modified_text": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "type": get_file_type(path.name),
            })

    return sorted(files, key=lambda item: item["modified"], reverse=True)


def authenticated():
    return session.get("authenticated") is True


@app.before_request
def protect_routes():
    public_endpoints = {"login", "static", "qr_code"}

    if request.endpoint in public_endpoints:
        return None

    if not authenticated():
        if request.path.startswith("/api/") or request.path == "/upload":
            return jsonify({"ok": False, "message": "Authentication required."}), 401
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        pin = request.form.get("pin", "").strip()

        if secrets.compare_digest(pin, ACCESS_PIN):
            session["authenticated"] = True
            return redirect(url_for("index"))

        error = "Incorrect PIN."

    return render_template("login.html", error=error)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
def index():
    lan_ip = get_local_ip()
    share_url = f"http://{lan_ip}:{PORT}"

    return render_template(
        "index.html",
        files=get_file_list(),
        share_url=share_url,
        lan_ip=lan_ip,
        port=PORT,
    )


@app.post("/upload")
def upload():
    incoming_files = request.files.getlist("files")

    if not incoming_files:
        return jsonify({"ok": False, "message": "No files received."}), 400

    saved_files = []

    for uploaded_file in incoming_files:
        if not uploaded_file or not uploaded_file.filename:
            continue

        safe_name = secure_filename(uploaded_file.filename)
        if not safe_name:
            safe_name = "uploaded_file"

        destination = make_unique_path(UPLOAD_FOLDER, safe_name)
        uploaded_file.save(destination)

        saved_files.append({
            "name": destination.name,
            "size": destination.stat().st_size,
        })

    if not saved_files:
        return jsonify({"ok": False, "message": "No valid files received."}), 400

    return jsonify({
        "ok": True,
        "message": f"Uploaded {len(saved_files)} file(s).",
        "files": saved_files,
    })


@app.get("/download/<path:filename>")
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@app.post("/api/delete")
def delete_file():
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")

    safe_name = secure_filename(filename)

    if not safe_name or safe_name != filename:
        return jsonify({"ok": False, "message": "Invalid filename."}), 400

    target = UPLOAD_FOLDER / safe_name

    if not target.exists() or not target.is_file():
        return jsonify({"ok": False, "message": "File not found."}), 404

    target.unlink()

    return jsonify({"ok": True, "message": "File deleted."})


@app.get("/api/files")
def api_files():
    return jsonify({"ok": True, "files": get_file_list()})


@app.get("/qr")
def qr_code():
    """
    Public QR image. It only contains the LAN URL, not the PIN.
    """
    share_url = f"http://{get_local_ip()}:{PORT}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(share_url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return app.response_class(buffer.getvalue(), mimetype="image/png")


if __name__ == "__main__":
    lan_ip = get_local_ip()

    print()
    print("=" * 58)
    print("            Wi-Fi File Share")
    print("=" * 58)
    print(f"Laptop:    http://127.0.0.1:{PORT}")
    print(f"Other Device:    http://{lan_ip}:{PORT}")
    print(f"PIN:       {ACCESS_PIN}")
    print()
    print("Open the laptop page to show the QR code.")
    print("Use only on a Wi-Fi network you trust.")
    print("Max 10Gb files are accectable.")
    print("Press Ctrl+C to stop the server.")
    print("=" * 58)
    print()

    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
