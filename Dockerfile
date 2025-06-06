FROM python:3.11-slim

WORKDIR /app

# Copy common requirements first to leverage Docker cache
COPY common/requirements.txt ./common/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r ./common/requirements.txt

# Copy common modules
COPY common ./common

# Copy the service specified at build time
ARG SERVICE_DIR
COPY services/${SERVICE_DIR} ./services/${SERVICE_DIR}

# Service-specific 
ENV SERVICE_NAME=${SERVICE_DIR}
ENV PYTHONPATH=/app

# Default command - will be overridden in the service Dockerfile
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 