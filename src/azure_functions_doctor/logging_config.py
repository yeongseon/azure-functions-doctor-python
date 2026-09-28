"""
Centralized logging configuration for Azure Functions Doctor.

This module provides a consistent logging setup across the entire application,
with environment-aware defaults and CLI integration.
"""

import logging
import os
import sys

# Default logger name for the application
DEFAULT_LOGGER_NAME = "azure_functions_doctor"

# Environment variable to override log level
LOG_LEVEL_ENV_VAR = "AZURE_FUNCTIONS_DOCTOR_LOG_LEVEL"


def setup_logging(
    level: str | None = None,
    format_style: str = "structured",
    enable_console_output: bool = True,
) -> logging.Logger:
    """
    Setup centralized logging configuration for the application.

    Args:
        level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR').
               If None, uses environment variable or defaults to WARNING.
        format_style: Logging format style - 'structured' or 'simple'
        enable_console_output: Whether to output logs to console (stderr)

    Returns:
        Configured root logger for the application
    """
    # Determine log level
    if level is None:
        level = os.getenv(LOG_LEVEL_ENV_VAR, "WARNING").upper()

    # Validate log level
    numeric_level = getattr(logging, level, None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.WARNING

    # Get or create the main application logger
    logger = logging.getLogger(DEFAULT_LOGGER_NAME)

    # If already configured, update level and formatter on existing handlers
    if logger.handlers:
        logger.setLevel(numeric_level)
        if format_style == "structured":
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
        else:  # simple
            formatter = logging.Formatter("%(levelname)s: %(message)s")
        for handler in logger.handlers:
            handler.setLevel(numeric_level)
            handler.setFormatter(formatter)
        # Honor enable_console_output: remove StreamHandlers when disabled
        if not enable_console_output:
            for handler in list(logger.handlers):
                if isinstance(handler, logging.StreamHandler):
                    logger.removeHandler(handler)
                    handler.close()
        logger.propagate = False
        return logger

    logger.setLevel(numeric_level)

    # Configure console handler (to stderr to avoid mixing with CLI output)
    if enable_console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(numeric_level)

        # Choose format based on style
        if format_style == "structured":
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
        else:  # simple
            formatter = logging.Formatter("%(levelname)s: %(message)s")

        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Logger instance that inherits from the main application logger
    """
    # Create hierarchical logger under the main application logger
    if not name.startswith(DEFAULT_LOGGER_NAME):
        name = f"{DEFAULT_LOGGER_NAME}.{name.split('.')[-1]}"

    return logging.getLogger(name)


def set_log_level(level: str) -> None:
    """
    Dynamically change the log level for the application.

    Args:
        level: New log level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        return

    # Update main logger and all its handlers
    main_logger = logging.getLogger(DEFAULT_LOGGER_NAME)
    main_logger.setLevel(numeric_level)

    for handler in main_logger.handlers:
        handler.setLevel(numeric_level)


def configure_for_testing() -> None:
    """
    Configure logging for test environments.
    Reduces noise and formats appropriately for test output.
    """
    # Set up minimal logging for tests
    setup_logging(level="CRITICAL", format_style="simple", enable_console_output=False)


def is_debug_enabled() -> bool:
    """
    Check if debug logging is currently enabled.

    Returns:
        True if debug level logging is enabled
    """
    main_logger = logging.getLogger(DEFAULT_LOGGER_NAME)
    return main_logger.isEnabledFor(logging.DEBUG)


def log_diagnostic_start(path: str, rules_count: int) -> None:
    """
    Log the start of a diagnostic session.

    Args:
        path: Path being diagnosed
        rules_count: Number of rules being executed
    """
    logger = get_logger(__name__)
    logger.info(f"Starting diagnostics for path: {path}")
    logger.info(f"Executing {rules_count} diagnostic rules")


def log_diagnostic_complete(
    total_checks: int, passed: int, failed: int, errors: int, duration_ms: float
) -> None:
    """
    Log the completion of a diagnostic session.

    Args:
        total_checks: Total number of checks executed
        passed: Number of checks that passed
        failed: Number of checks that failed
        errors: Number of checks that had errors
        duration_ms: Execution time in milliseconds
    """
    logger = get_logger(__name__)
    logger.info(f"Diagnostics completed in {duration_ms:.1f}ms")
    logger.info(
        f"Results: {passed} passed, {failed} failed, {errors} errors out of {total_checks} total"
    )

    if errors > 0:
        logger.warning(f"Encountered {errors} unexpected errors during execution")


def log_rule_execution(rule_id: str, rule_type: str, status: str, duration_ms: float) -> None:
    """
    Log the execution of an individual rule.

    Args:
        rule_id: Rule identifier
        rule_type: Type of check being performed
        status: Result status ('pass', 'fail', 'error')
        duration_ms: Execution time in milliseconds
    """
    logger = get_logger(__name__)
    if status == "error":
        logger.warning(f"Rule {rule_id} ({rule_type}) completed with error in {duration_ms:.1f}ms")
    else:
        logger.debug(f"Rule {rule_id} ({rule_type}) -> {status} ({duration_ms:.1f}ms)")
