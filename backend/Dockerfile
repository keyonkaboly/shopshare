FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY envDependencies.txt .
RUN pip install --no-cache-dir -r envDependencies.txt

COPY . .

EXPOSE 8000

# Render (and most PaaS hosts) inject a $PORT env var and require the app to
# bind to it — it's not always 8000. Falls back to 8000 for local
# `docker compose up`, which doesn't set PORT and expects the old fixed port.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
