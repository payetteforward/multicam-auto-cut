"""Logging configuration for the application."""

import logging
import sys
from typing import Optional


def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """
    Configure logging for the application.

    Args:
        verbose: Enable verbose (DEBUG) logging
        log_file: Optional path to log file
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    # Try to use colorlog if available
    try:
        import colorlog

        # Console handler with colors
        console_handler = colorlog.StreamHandler()
        console_handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)-15s%(reset)s %(message)s",
                datefmt=None,
                reset=True,
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )
        )
    except ImportError:
        # Fallback to standard formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("%(levelname)-8s %(name)-15s %(message)s")
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        root_logger.addHandler(file_handler)

    # Set specific logger levels
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)