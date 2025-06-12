import logging
import sys
from typing import Optional
from datetime import datetime


# Configure logging format
class CustomFormatter(logging.Formatter):
    """Custom formatter with timestamp and service name"""

    def format(self, record):
        record.timestamp = datetime.utcnow().isoformat()
        record.service = getattr(record, "service", "unknown")
        return super().format(record)


def setup_logging(service_name: str, log_level: Optional[str] = None) -> logging.Logger:
    """Setup structured logging for a service"""

    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(log_level or logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level or logging.INFO)

    # Create formatter
    formatter = CustomFormatter(
        "%(timestamp)s [%(service)s] %(levelname)s: %(message)s"
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    # Add service name to all log records
    logger = logging.LoggerAdapter(logger, {"service": service_name})

    return logger
