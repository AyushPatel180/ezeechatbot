"""Simple, readable logging for EzeeChatBot."""
import logging
import sys

from app.config import settings

LOG_FILE_PATH = "/app/logs/ezeechatbot.log"


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')
        location = f"{record.name}:{record.lineno}" if hasattr(record, 'lineno') else record.name
        return f"{log_color}[{timestamp}] [{record.levelname:8}] [{location:25}] {record.getMessage()}{self.RESET}"


class FileFormatter(logging.Formatter):
    """Clean formatter for file output."""
    
    def format(self, record):
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')
        location = f"{record.name}:{record.lineno}" if hasattr(record, 'lineno') else record.name
        return f"[{timestamp}] [{record.levelname:8}] [{location:25}] {record.getMessage()}"


# Global flag to track if logging is configured
_is_configured = False


class StructuredLogger:
    """Small wrapper that accepts structured keyword fields."""

    _RESERVED_KEYS = {"exc_info", "stack_info", "stacklevel", "extra"}

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: str, message: str, *args, **kwargs):
        reserved = {key: kwargs.pop(key) for key in list(kwargs.keys()) if key in self._RESERVED_KEYS}
        if kwargs:
            context = " ".join(f"{key}={value}" for key, value in sorted(kwargs.items()))
            message = f"{message} | {context}"
        getattr(self._logger, level)(message, *args, **reserved)

    def debug(self, message: str, *args, **kwargs):
        self._log("debug", message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._log("info", message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._log("warning", message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._log("error", message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._log("critical", message, *args, **kwargs)


def configure_logging():
    """Configure readable logging for the application."""
    global _is_configured
    if _is_configured:
        return
    
    log_level = getattr(logging, settings.LOG_LEVEL.upper())
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredFormatter())
    
    # File handler without colors
    file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(FileFormatter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    _is_configured = True


def get_logger(name: str):
    """Get a logger instance."""
    configure_logging()  # Ensure logging is configured
    return StructuredLogger(logging.getLogger(name))
