"""
Centralized Logging System for E-commerce Saga

This module provides structured logging with correlation IDs,
JSON formatting, rotating file handlers, and centralized log aggregation.
Later to be replaced by observability platforms like ELK, Prometheus, etc.
"""

import logging
import logging.handlers
import json
import sys
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from functools import wraps
import traceback
from enum import Enum
import os
from pathlib import Path

# Context variables for correlation tracking
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default=None)
request_id_var: ContextVar[str] = ContextVar("request_id", default=None)


class EventType(Enum):
    """Standard event types for structured logging"""

    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    SAGA_START = "saga_start"
    SAGA_STEP = "saga_step"
    SAGA_COMPLETE = "saga_complete"
    SAGA_FAILED = "saga_failed"
    SAGA_COMPENSATE = "saga_compensate"
    DATABASE_OPERATION = "database_operation"
    SERVICE_CALL = "service_call"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    HEALTH_CHECK = "health_check"
    PERFORMANCE = "performance"
    SECURITY = "security"
    BUSINESS_EVENT = "business_event"


class LogLevel(Enum):
    """Log levels"""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class CorrelationLogRecord(logging.LogRecord):
    """Enhanced log record with correlation tracking"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add correlation context
        self.correlation_id = correlation_id_var.get()
        self.request_id = request_id_var.get()
        self.timestamp_iso = datetime.utcnow().isoformat() + "Z"


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        log_entry = {
            "timestamp": getattr(
                record, "timestamp_iso", datetime.utcnow().isoformat() + "Z"
            ),
            "service": self.service_name,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process,
        }

        # Add correlation IDs if available
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_entry["correlation_id"] = record.correlation_id
        if hasattr(record, "request_id") and record.request_id:
            log_entry["request_id"] = record.request_id

        # Add event type if specified
        if hasattr(record, "event_type"):
            log_entry["event_type"] = record.event_type

        # Add extra fields
        if hasattr(record, "extra_data") and record.extra_data:
            log_entry["extra"] = record.extra_data

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with colors"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def __init__(self, service_name: str, use_colors: bool = True):
        super().__init__()
        self.service_name = service_name
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        timestamp = getattr(record, "timestamp_iso", datetime.utcnow().isoformat())
        correlation_id = getattr(record, "correlation_id", None)

        # Build message
        parts = [
            timestamp[:19],  # Truncate microseconds
            f"[{self.service_name}]",
            f"{record.levelname:8}",
            f"{record.name}",
            record.getMessage(),
        ]

        if correlation_id:
            parts.insert(-1, f"[{correlation_id[:8]}]")

        message = " ".join(parts)

        # Add color if enabled
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
            message = f"{color}{message}{reset}"

        # Add exception info
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


class CentralizedLogger:
    """Main logger class with correlation tracking and rotating files"""

    def __init__(self, service_name: str, log_level: LogLevel = LogLevel.INFO):
        self.service_name = service_name
        self.log_level = log_level
        self.logger = logging.getLogger(f"saga.{service_name}")
        self.logger.setLevel(log_level.value)
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup file and console handlers"""
        # Clear existing handlers
        self.logger.handlers.clear()

        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # 1. Rotating File Handler - JSON format
        json_file_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / f"{self.service_name}.json.log",
            maxBytes=100 * 1024,  # 100KB
            backupCount=5,
            encoding="utf-8",
        )
        json_file_handler.setLevel(self.log_level.value)
        json_file_handler.setFormatter(JSONFormatter(self.service_name))

        # 2. Rotating File Handler - Human readable format
        text_file_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / f"{self.service_name}.log",
            maxBytes=100 * 1024,  # 100KB
            backupCount=5,
            encoding="utf-8",
        )
        text_file_handler.setLevel(self.log_level.value)
        text_file_handler.setFormatter(
            ConsoleFormatter(self.service_name, use_colors=False)
        )

        # 3. Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level.value)
        console_handler.setFormatter(
            ConsoleFormatter(self.service_name, use_colors=True)
        )

        # Add handlers
        self.logger.addHandler(json_file_handler)
        self.logger.addHandler(text_file_handler)
        self.logger.addHandler(console_handler)

        # Set custom record factory
        logging.setLogRecordFactory(CorrelationLogRecord)

    def _log(
        self,
        level: LogLevel,
        event_type: EventType,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ):
        """Internal logging method"""
        extra = {"event_type": event_type.value, "extra_data": extra_data or {}}

        self.logger.log(level.value, message, extra=extra, exc_info=exc_info)

    def debug(
        self,
        event_type: EventType,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Log debug message"""
        self._log(LogLevel.DEBUG, event_type, message, extra)

    def info(
        self,
        event_type: EventType,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Log info message"""
        self._log(LogLevel.INFO, event_type, message, extra)

    def warning(
        self,
        event_type: EventType,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Log warning message"""
        self._log(LogLevel.WARNING, event_type, message, extra)

    def error(
        self,
        event_type: EventType,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = True,
    ):
        """Log error message"""
        self._log(LogLevel.ERROR, event_type, message, extra, exc_info)

    def critical(
        self,
        event_type: EventType,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = True,
    ):
        """Log critical message"""
        self._log(LogLevel.CRITICAL, event_type, message, extra, exc_info)


# Global logger registry
_loggers: Dict[str, CentralizedLogger] = {}


def get_logger(
    service_name: str, log_level: LogLevel = LogLevel.INFO
) -> CentralizedLogger:
    """Get or create logger for service"""
    if service_name not in _loggers:
        _loggers[service_name] = CentralizedLogger(service_name, log_level)
    return _loggers[service_name]


def set_correlation_id(correlation_id: str):
    """Set correlation ID for current context"""
    correlation_id_var.set(correlation_id)


def set_request_id(request_id: str):
    """Set request ID for current context"""
    request_id_var.set(request_id)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID"""
    return correlation_id_var.get()


def get_request_id() -> Optional[str]:
    """Get current request ID"""
    return request_id_var.get()


def generate_correlation_id() -> str:
    """Generate new correlation ID"""
    return str(uuid.uuid4())


def with_correlation(correlation_id: Optional[str] = None):
    """Decorator to add correlation ID to function calls"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cid = correlation_id or generate_correlation_id()
            token = correlation_id_var.set(cid)
            try:
                return await func(*args, **kwargs)
            finally:
                correlation_id_var.reset(token)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cid = correlation_id or generate_correlation_id()
            token = correlation_id_var.set(cid)
            try:
                return func(*args, **kwargs)
            finally:
                correlation_id_var.reset(token)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# Convenience functions for backward compatibility
def setup_logging(service_name: str, log_level: str = "INFO") -> CentralizedLogger:
    """Setup logging for a service (backward compatibility)"""
    level_map = {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARNING": LogLevel.WARNING,
        "ERROR": LogLevel.ERROR,
        "CRITICAL": LogLevel.CRITICAL,
    }
    level = level_map.get(log_level.upper(), LogLevel.INFO)
    return get_logger(service_name, level)


# Import asyncio for decorator
import asyncio
