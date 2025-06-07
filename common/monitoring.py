from prometheus_client import Counter, Histogram, start_http_server
import time
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

# Metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"]
)


# Tracing setup
def setup_tracing(service_name: str):
    """Setup OpenTelemetry tracing if available"""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer(__name__)

        # Configure OTLP exporter
        otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)

        # Add span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)

        logger.info("OpenTelemetry tracing enabled")
        return tracer
    except ImportError:
        logger.warning("OpenTelemetry dependencies not found. Tracing disabled.")
        return None


def instrument_fastapi(app: FastAPI, service_name: str):
    """Instrument FastAPI application with OpenTelemetry if available"""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation enabled")
    except ImportError:
        logger.warning("OpenTelemetry FastAPI instrumentation not available")


def start_metrics_server(port: int = 8000):
    """Start Prometheus metrics server"""
    start_http_server(port)
    logger.info(f"Metrics server started on port {port}")


class RequestMetrics:
    """Middleware for collecting request metrics"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        start_time = time.time()

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                # Record request count
                REQUEST_COUNT.labels(
                    method=scope["method"],
                    endpoint=scope["path"],
                    status=message["status"],
                ).inc()

                # Record request latency
                REQUEST_LATENCY.labels(
                    method=scope["method"], endpoint=scope["path"]
                ).observe(time.time() - start_time)

            await send(message)

        await self.app(scope, receive, wrapped_send)
