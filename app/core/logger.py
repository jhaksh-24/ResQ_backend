"""
ResQ — Structured Analytics Logger
====================================
A unified logging utility designed to output structured JSON
or formatted text for analytics, monitoring, and debugging.

Logs are critical for data pipelines to trace routing decisions,
dispatch latencies, and fleet rebalancing events.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict

from app.config import get_settings

settings = get_settings()

class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured ingestion (e.g., ELK, Datadog)."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        
        # Add any extra attributes passed via 'extra' dict
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)
            
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

class DevFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        if hasattr(record, "extra_data") and record.extra_data:
            base += f" | {record.extra_data}"
        return base

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance.
    Uses JSON formatting in production, structured text in development.
    """
    logger = logging.getLogger(name)
    
    # Only configure if no handlers exist to avoid duplicate logs
    if not logger.handlers:
        logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        logger.propagate = False
        
        handler = logging.StreamHandler()
        
        if settings.APP_ENV == "production":
            handler.setFormatter(JSONFormatter())
        else:
            # Clean text format for local development
            formatter = DevFormatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            
        logger.addHandler(handler)
        
    return logger

def log_event(logger: logging.Logger, level: int, message: str, **kwargs):
    """
    Helper to safely log with structured extra data.
    Usage:
        log_event(logger, logging.INFO, "Dispatch successful", unit_id=5, eta=120)
    """
    logger.log(level, message, extra={"extra_data": kwargs})
