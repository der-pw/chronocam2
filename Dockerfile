# syntax=docker/dockerfile:1
FROM python:3.12-alpine

# Install system dependencies for building Python packages
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app ./app

# Create a non-root user to run the application and ensure writable app directory
RUN adduser -D appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
