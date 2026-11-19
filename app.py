import os
import uuid
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024

FFMPEG_PATH = shutil.which("ffmpeg")
FFPROBE_PATH = shutil.which("ffprobe")

if not FFMPEG_PATH or not FFPROBE_PATH:
    raise RuntimeError(
        "FFmpeg and FFprobe must be installed and available in PATH. "
        "Open a NEW terminal after updating Windows PATH, then run "
        "'ffmpeg -version' and 'ffprobe -version'."
    )

FFMPEG_DIR = str(Path(FFMPEG_PATH).parent)
print("FFmpeg detected:", FFMPEG_PATH)
print("FFprobe detected:", FFPROBE_PATH)

ALLOWED_EXTENSIONS = {
    "mp3", "wav", "aac", "m4a", "ogg", "flac",
    "mp4", "mkv", "mov", "webm", "avi"
}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_uploaded_file(file):
    if not file or not file.filename:
        raise ValueError("Please choose an audio or video file.")

    original_name = secure_filename(file.filename)
    if not original_name or not allowed_file(original_name):
        raise ValueError("Unsupported file format.")

    extension = Path(original_name).suffix.lower()
    destination = UPLOAD_DIR / f"{uuid.uuid4().hex}{extension}"
    file.save(destination)

    if not destination.is_file() or destination.stat().st_size == 0:
        raise ValueError("The uploaded file is empty or could not be saved.")

    return destination


def get_input_file():
    uploaded = request.files.get("file")
    if uploaded:
        return save_uploaded_file(uploaded)

    if request.is_json:
        data = request.get_json(silent=True) or {}
        filename = data.get("filename", "")
        if not filename or Path(filename).name != filename:
            raise ValueError("Invalid input filename.")

        source = UPLOAD_DIR / filename
        if not source.is_file():
            raise ValueError("Uploaded file not found. Please upload it again.")
        return source

    raise ValueError("Please select a media file before processing.")


def get_streams(source):
    command = [
        FFPROBE_PATH, "-v", "error",
        "-show_entries", "stream=codec_type",
        "-of", "json", str(source)
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise ValueError("The selected file is not a readable audio/video file.")

    import json
    details = json.loads(result.stdout or "{}")
    types = {stream.get("codec_type") for stream in details.get("streams", [])}
    return "video" in types, "audio" in types


def run_ffmpeg(args):
    result = subprocess.run(
        [FFMPEG_PATH, "-hide_banner", "-loglevel", "error", "-y"] + args,
        capture_output=True,
        text=True,
        timeout=600
    )
    if result.returncode != 0:
        message = (result.stderr or "FFmpeg could not process this file.").strip()
        raise RuntimeError(message[-1800:])


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    try:
        source = save_uploaded_file(request.files.get("file"))
        return jsonify(
            message="File uploaded successfully.",
            filename=source.name
        )
    except Exception as error:
        return jsonify(error=str(error)), 400


@app.route("/convert", methods=["POST"])
def convert():
    try:
        source = get_input_file()
        has_video, has_audio = get_streams(source)

        if request.is_json:
            data = request.get_json(silent=True) or {}
            operation = str(data.get("operation", "")).lower()
        else:
            operation = request.form.get("operation", "").lower()

        # Keep compatibility with the earlier frontend operation names.
        if operation == "extract_audio":
            operation = "mp3"
        if operation in ("mute", "extract_video"):
            operation = "video_only"

        supported = {"mp3", "wav", "mp4", "video_only", "keep_audio"}
        if operation not in supported:
            return jsonify(error="Choose a valid media operation."), 400

        job_id = uuid.uuid4().hex

        if operation in ("mp3", "wav"):
            if not has_audio:
                return jsonify(error="This file does not contain an audio track."), 400

            extension = "mp3" if operation == "mp3" else "wav"
            output = OUTPUT_DIR / f"{job_id}.{extension}"
            args = ["-i", str(source), "-map", "0:a:0", "-vn"]

            if operation == "mp3":
                args += ["-c:a", "libmp3lame", "-q:a", "2"]
            else:
                args += ["-c:a", "pcm_s16le"]

            args.append(str(output))

        elif operation == "mp4":
            if not has_video:
                return jsonify(error="MP4 conversion requires a video file."), 400

            output = OUTPUT_DIR / f"{job_id}.mp4"
            args = [
                "-i", str(source),
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output)
            ]

        elif operation == "video_only":
            if not has_video:
                return jsonify(error="Removing audio requires a video file."), 400

            output = OUTPUT_DIR / f"{job_id}.mp4"
            args = [
                "-i", str(source),
                "-map", "0:v:0",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-an",
                "-movflags", "+faststart",
                str(output)
            ]

        else:  # keep_audio
            if not has_video:
                return jsonify(error="This operation requires a video file."), 400

            output = OUTPUT_DIR / f"{job_id}.mp4"
            args = [
                "-i", str(source),
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output)
            ]

        run_ffmpeg(args)

        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("The processed output file was not created.")

        return jsonify(
            message="Media processing completed successfully.",
            download=f"/download/{output.name}"
        )

    except subprocess.TimeoutExpired:
        return jsonify(error="Processing took too long. Try a shorter or smaller file."), 408
    except Exception as error:
        return jsonify(error=str(error)[:1200]), 400


@app.route("/trim", methods=["POST"])
def trim():
    try:
        source = get_input_file()
        has_video, has_audio = get_streams(source)

        if request.is_json:
            data = request.get_json(silent=True) or {}
            start = float(data.get("start", 0))
            end = float(data.get("end", 0))
        else:
            start = float(request.form.get("start", 0))
            end = float(request.form.get("end", 0))

        if start < 0 or end <= start or end - start > 3600:
            return jsonify(
                error="Enter valid start and end times. The maximum trim length is 60 minutes."
            ), 400

        job_id = uuid.uuid4().hex

        if has_video:
            # Re-encoding gives more accurate cut points than stream-copy trimming.
            output = OUTPUT_DIR / f"{job_id}.mp4"
            args = [
                "-ss", str(start),
                "-i", str(source),
                "-t", str(end - start),
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output)
            ]
        elif has_audio:
            # Audio trim is exported as MP3 for a predictable download format.
            output = OUTPUT_DIR / f"{job_id}.mp3"
            args = [
                "-ss", str(start),
                "-i", str(source),
                "-t", str(end - start),
                "-map", "0:a:0",
                "-vn",
                "-c:a", "libmp3lame",
                "-q:a", "2",
                str(output)
            ]
        else:
            return jsonify(error="No audio or video stream was found in this file."), 400

        run_ffmpeg(args)

        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("The trimmed output file was not created.")

        return jsonify(
            message="Trimming completed successfully.",
            download=f"/download/{output.name}"
        )

    except ValueError as error:
        return jsonify(error=str(error)), 400
    except subprocess.TimeoutExpired:
        return jsonify(error="Trimming took too long. Try a shorter file."), 408
    except Exception as error:
        return jsonify(error=str(error)[:1200]), 400


@app.route("/url-convert", methods=["POST"])
def url_convert():
    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "")
        operation = str(data.get("operation", "")).lower()

        if not isinstance(url, str):
            return jsonify(error="Please enter a valid HTTPS URL."), 400

        url = url.strip()
        parsed = urlparse(url)

        if parsed.scheme != "https" or not parsed.hostname:
            return jsonify(error="Please enter a valid HTTPS URL."), 400

        if operation not in ("mp3", "mp4"):
            return jsonify(error="Please select MP3 or MP4."), 400

        job_id = uuid.uuid4().hex
        output_template = str(OUTPUT_DIR / f"{job_id}.%(ext)s")

        options = {
            "outtmpl": output_template,
            "noplaylist": True,
            "ffmpeg_location": FFMPEG_DIR,
            "socket_timeout": 30,
            "retries": 2,
            "quiet": True,
            "no_warnings": True,
            "max_filesize": 300 * 1024 * 1024
        }

        if operation == "mp3":
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
            expected_output = OUTPUT_DIR / f"{job_id}.mp3"
        else:
            options["format"] = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            )
            options["merge_output_format"] = "mp4"
            expected_output = OUTPUT_DIR / f"{job_id}.mp4"

        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([url])

        if not expected_output.is_file():
            raise RuntimeError(
                "The output file was not created. This source may not provide "
                "the selected format or may not be supported by yt-dlp."
            )

        return jsonify(
            message=f"{operation.upper()} conversion completed successfully.",
            download=f"/download/{expected_output.name}"
        )

    except Exception as error:
        return jsonify(error=f"URL processing failed: {str(error)[:700]}"), 400


@app.route("/download/<filename>")
def download(filename):
    if Path(filename).name != filename:
        return jsonify(error="Invalid filename."), 400

    file_path = OUTPUT_DIR / filename
    if not file_path.is_file():
        return jsonify(error="File not found. Please process the media again."), 404

    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


@app.errorhandler(413)
def file_too_large(error):
    return jsonify(error="Maximum upload size is 300 MB."), 413


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000))
    )
