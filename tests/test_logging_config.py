import logging
from typing import TYPE_CHECKING

from azure_functions_doctor import logging_config

if TYPE_CHECKING:
    import pytest


def _reset_main_logger() -> logging.Logger:
    logger = logging.getLogger(logging_config.DEFAULT_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    return logger


def test_setup_logging_uses_environment_level(monkeypatch: "pytest.MonkeyPatch") -> None:
    _reset_main_logger()
    monkeypatch.setenv(logging_config.LOG_LEVEL_ENV_VAR, "INFO")

    logger = logging_config.setup_logging(level=None, format_style="simple")

    assert logger.level == logging.INFO
    assert logger.propagate is False
    assert len(logger.handlers) == 1
    assert logger.handlers[0].formatter is not None
    assert logger.handlers[0].formatter._fmt == "%(levelname)s: %(message)s"


def test_setup_logging_invalid_level_and_existing_handlers() -> None:
    logger = _reset_main_logger()
    logger.addHandler(logging.NullHandler())

    configured = logging_config.setup_logging(level="NOT_A_LEVEL")

    assert configured is logger
    assert len(configured.handlers) == 1


def test_setup_logging_without_console_output() -> None:
    _reset_main_logger()

    configured = logging_config.setup_logging(level="DEBUG", enable_console_output=False)

    assert configured.level == logging.DEBUG
    assert configured.handlers == []
    assert configured.propagate is False


def test_get_logger_normalizes_name() -> None:
    logger = logging_config.get_logger("custom.module")

    assert logger.name == "azure_functions_doctor.module"


def test_set_log_level_and_debug_helpers() -> None:
    logger = _reset_main_logger()
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    logging_config.set_log_level("DEBUG")
    assert logger.level == logging.DEBUG
    assert handler.level == logging.DEBUG
    assert logging_config.is_debug_enabled() is True

    logging_config.set_log_level("INVALID")
    assert logger.level == logging.DEBUG

    _reset_main_logger()
    logging_config.configure_for_testing()
    assert logging.getLogger(logging_config.DEFAULT_LOGGER_NAME).level == logging.CRITICAL


def test_log_helper_functions(monkeypatch: "pytest.MonkeyPatch") -> None:
    class DummyLogger:
        def __init__(self) -> None:
            self.info_messages: list[str] = []
            self.warning_messages: list[str] = []
            self.debug_messages: list[str] = []

        def info(self, message: str) -> None:
            self.info_messages.append(message)

        def warning(self, message: str) -> None:
            self.warning_messages.append(message)

        def debug(self, message: str) -> None:
            self.debug_messages.append(message)

    dummy = DummyLogger()
    monkeypatch.setattr(logging_config, "get_logger", lambda name: dummy)

    logging_config.log_diagnostic_start("/tmp/app", 4)
    logging_config.log_diagnostic_complete(4, 3, 1, 1, 12.5)
    logging_config.log_rule_execution("rule-1", "env_var_exists", "error", 10.0)
    logging_config.log_rule_execution("rule-2", "env_var_exists", "pass", 5.0)

    assert any("Starting diagnostics" in msg for msg in dummy.info_messages)
    assert any("Results: 3 passed, 1 failed, 1 errors" in msg for msg in dummy.info_messages)
    assert any("Encountered 1 unexpected errors" in msg for msg in dummy.warning_messages)
    assert any("completed with error" in msg for msg in dummy.warning_messages)
    assert any("-> pass" in msg for msg in dummy.debug_messages)


def test_setup_logging_removes_stream_handlers_when_console_disabled() -> None:
    logger = _reset_main_logger()
    logger.addHandler(logging.StreamHandler())

    configured = logging_config.setup_logging(level="INFO", enable_console_output=False)

    assert configured.handlers == []


def test_setup_logging_structured_formatter() -> None:
    logger = _reset_main_logger()

    configured = logging_config.setup_logging(level="INFO", format_style="structured")

    assert configured.handlers
    formatter = configured.handlers[0].formatter
    assert formatter is not None
    assert isinstance(formatter._fmt, str)
    assert "%(asctime)s" in formatter._fmt
