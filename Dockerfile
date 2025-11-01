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

<<<<<<< HEAD
# Create a non-root user and fix ownership of relevant directories
RUN adduser -D appuser \
    && chown -R appuser:appuser /app

=======
# Create a non-root user to run the application and ensure writable app directory
RUN adduser -D appuser \
    && chown -R appuser:appuser /app
>>>>>>> 11de5cbed9c9389491fe4e2a9a5b87bf5808c945
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

