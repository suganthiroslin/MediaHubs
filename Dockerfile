
FROM python:3.11-slim

WORKDIR /app

# Install FFmpeg and FFprobe
RUN apt-get update && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend project files
COPY . .

# Create upload and output folders
RUN mkdir -p uploads outputs

# Start Flask using Gunicorn
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-10000}"]
