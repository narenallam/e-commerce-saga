FROM ../../Dockerfile

ARG SERVICE_DIR=order
ENV PORT=8000

COPY ../../coordinator ./coordinator

WORKDIR /app/services/order

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT}"] 