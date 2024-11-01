FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY service-account.json /app/service-account.json

ENV PYTHONPATH=/app

CMD ["./docker-entrypoint.sh"]