FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install alembic

COPY . .

RUN chmod +x /app/docker-entrypoint.sh

ENV PATH="/app:${PATH}"

CMD ["/app/docker-entrypoint.sh"]