FROM python:3.11-slim

# Install system dependencies (FFmpeg is critical for Auteur's video processing)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Expose FastAPI default port
EXPOSE 8000

# Start command (Overridden on Render for the background worker)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
