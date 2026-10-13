# Dockerfile for Bothost (and any Docker host). ASCII-only comments on purpose.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/app/data/sto_bot.db

# Code lives outside /app: Bothost may bind-mount /app, which would hide the image contents.
WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent data (SQLite) lives in /app/data
RUN mkdir -p /app/data && chmod 777 /app/data

CMD ["python", "bot.py"]
