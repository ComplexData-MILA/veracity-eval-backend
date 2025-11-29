FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /models

COPY . .

ENV PYTHONPATH=/app

ENV HF_HOME="/app/hf_cache"

# 4. RUN THE PRELOAD SCRIPT
# This downloads the 80MB model and saves it into the image layers
RUN python app/preload_model.py

CMD ["./docker-entrypoint.sh"]