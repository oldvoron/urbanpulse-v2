FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Cloud Run injects PORT (default 8080); shell form so ${PORT} expands at start.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
