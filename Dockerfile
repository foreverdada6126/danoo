FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y git build-essential curl docker.io procps && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure storage exists
RUN mkdir -p logs data database reference_files

EXPOSE 8000

CMD ["python", "app.py"]
