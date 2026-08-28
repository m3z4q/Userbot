FROM python:3.11-slim

WORKDIR /app

# System dependencies for Pillow, pycryptodome, etc
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Create sessions directory
RUN mkdir -p sessions

# Run bot
CMD ["python", "bot.py"]
