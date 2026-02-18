# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (needed for some LangChain/OpenClaw tools)
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir langchain langchain-community langchain-openai

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p logs data/raw data/processed data/cache database reference_files

# Expose Web UI port
EXPOSE 8000

# Start command
# We run the DaNoo app which initializes the OpenClaw logic internally
CMD ["python", "app.py"]
