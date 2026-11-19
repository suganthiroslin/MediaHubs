# MediaHub - Local setup

## Folder structure

Keep the files in this structure:

MediaHub/
  app.py
  requirements.txt
  templates/
    index.html
  static/
    style.css
    script.js
  uploads/       (created automatically)
  outputs/       (created automatically)

## 1. Install Python packages

Open Command Prompt inside the MediaHub folder and run:

    py -m venv venv
    venv\Scripts\activate
    py -m pip install -r requirements.txt

## 2. Check FFmpeg and FFprobe

Open a NEW Command Prompt and run:

    ffmpeg -version
    ffprobe -version

Both commands must display version information. If Windows says the command is not recognized, add the FFmpeg `bin` folder to PATH and open a new terminal.

## 3. Start the website

From the MediaHub folder, with the virtual environment activated, run:

    py app.py

Open this address in your browser:

    http://127.0.0.1:5000

Keep the Command Prompt window open while using the website.

## Supported actions

- URL to MP4 and URL to MP3 (through yt-dlp; supported sources only)
- Extract audio as MP3 or WAV
- Convert video to MP4
- Remove audio from a video (mute / video-only)
- Keep audio while converting video to MP4
- Trim video (exported as MP4)
- Trim audio (exported as MP3)

The 300 MB limit is enforced by the Flask server. Processing large files can take time.

Note: URL download support depends on the source website and its current restrictions.
