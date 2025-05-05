import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import logging.config

# Log levels
CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

class JSONFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON format
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if available
        if record.exc_info:
            log_record["exception"] = {
                "type": record.exc_info[0].__name__,
                "value": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
            
        # Add extra fields
        if hasattr(record, "extra"):
            log_record.update(record.extra)
            
        return json.dumps(log_record)

def get_logger(name: str, level: int = INFO) -> logging.Logger:
    """
    Get a logger instance with the specified name and level
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger

def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    """
    Configure logging for the application
    
    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: The directory to store log files
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Log levels
    level_map = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL
    }
    
    # Get the numeric log level
    numeric_level = level_map.get(log_level.upper(), INFO)
    
    # Configure logging
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter
            },
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": sys.stdout
            },
            "file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": log_path / "app.log",
                "maxBytes": 10485760,  # 10 MB
                "backupCount": 10
            },
            "error_file": {
                "level": "ERROR",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": log_path / "error.log",
                "maxBytes": 10485760,  # 10 MB
                "backupCount": 10
            }
        },
        "loggers": {
            "": {  # Root logger
                "handlers": ["console", "file", "error_file"],
                "level": numeric_level
            },
            "app": {
                "handlers": ["console", "file", "error_file"],
                "level": numeric_level,
                "propagate": False
            },
            "uvicorn": {
                "handlers": ["console", "file"],
                "level": numeric_level,
                "propagate": False
            },
            "sqlalchemy": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False
            }
        }
    }
    
    # Apply configuration
    logging.config.dictConfig(logging_config)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level}")

class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom logger adapter to add extra fields to log records
    """
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any] = None):
        super().__init__(logger, extra or {})
    
    def process(self, msg, kwargs):
        kwargs.setdefault('extra', {}).update(self.extra)
        return msg, kwargs

def get_request_logger(request_id: str, user_id: Optional[str] = None) -> LoggerAdapter:
    """
    Get a logger instance with request-specific context
    
    Args:
        request_id: The unique identifier for the request
        user_id: The ID of the authenticated user (if available)
        
    Returns:
        A logger adapter with the request-specific context
    """
    logger = logging.getLogger("app.request")
    extra = {
        "request_id": request_id,
        "user_id": user_id
    }
    return LoggerAdapter(logger, extra)