FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY config/requirements.txt ./config/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r ./config/requirements.txt \
    && pip install --no-cache-dir \
    opentelemetry-api==1.21.0 \
    opentelemetry-sdk==1.21.0 \
    opentelemetry-instrumentation-fastapi==0.42b0 \
    opentelemetry-exporter-otlp-proto-grpc==1.21.0

# Copy source code
COPY src ./src

# Copy the service specified at build time
ARG SERVICE_DIR

# Set environment variables
ENV SERVICE_NAME=${SERVICE_DIR}
ENV SERVICE_DIR=${SERVICE_DIR}
ENV PYTHONPATH=/app
ENV PORT=8000

# Command to run the service using the PORT environment variable
# Handle coordinator vs services differently
CMD if [ "$SERVICE_DIR" = "coordinator" ]; then \
        uvicorn src.coordinator.main:app --host 0.0.0.0 --port ${PORT}; \
    else \
        uvicorn src.services.${SERVICE_DIR}.main:app --host 0.0.0.0 --port ${PORT}; \
    fi 