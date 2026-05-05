"""Tests for configuration management."""

import os
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING

from azure_functions_doctor.config import Config, get_config, override_config

if TYPE_CHECKING:
    import pytest


def test_config_defaults() -> None:
    """Test that default configuration values are loaded."""
    config = Config()

    assert config.get("log_level") == "WARNING"
    assert config.get("log_format") == "simple"
    assert config.get("max_file_size_mb") == 10
    assert config.get("enable_colors") is True
    assert config.get("parallel_execution") is False


def test_config_environment_variables(monkeypatch: "pytest.MonkeyPatch") -> None:
    """Test loading configuration from environment variables."""
    monkeypatch.setenv("FUNC_DOCTOR_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("FUNC_DOCTOR_MAX_FILE_SIZE_MB", "20")
    monkeypatch.setenv("FUNC_DOCTOR_ENABLE_COLORS", "false")

    config = Config()

    assert config.get("log_level") == "DEBUG"
    assert config.get("max_file_size_mb") == 20
    assert config.get("enable_colors") is False


def test_config_boolean_environment_values(monkeypatch: "pytest.MonkeyPatch") -> None:
    """Test boolean environment variable parsing."""
    test_cases = [
        ("true", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
    ]

    for env_value, expected in test_cases:
        monkeypatch.setenv("FUNC_DOCTOR_ENABLE_COLORS", env_value)
        config = Config()
        assert config.get("enable_colors") is expected


def test_config_invalid_environment_values(monkeypatch: "pytest.MonkeyPatch") -> None:
    """Test handling of invalid environment variable values."""
    monkeypatch.setenv("FUNC_DOCTOR_MAX_FILE_SIZE_MB", "invalid")

    config = Config()

    # Should fall back to default value
    assert config.get("max_file_size_mb") == 10


def test_config_set_and_get() -> None:
    """Test setting and getting configuration values."""
    config = Config()

    config.set("test_key", "test_value")
    assert config.get("test_key") == "test_value"

    assert config.get("nonexistent_key", "default") == "default"


def test_config_convenience_methods() -> None:
    """Test convenience methods for common configuration values."""
    config = Config()

    assert isinstance(config.get_log_level(), str)
    assert isinstance(config.get_log_format(), str)
    assert isinstance(config.get_max_file_size_mb(), int)
    assert isinstance(config.get_search_timeout_seconds(), int)
    assert isinstance(config.get_rules_file(), str)
    assert isinstance(config.get_output_width(), int)
    assert isinstance(config.is_colors_enabled(), bool)
    assert isinstance(config.is_parallel_execution_enabled(), bool)


def test_config_custom_rules_path(monkeypatch: "pytest.MonkeyPatch") -> None:
    """Test custom rules path resolution."""
    config = Config()

    # No custom path set
    assert config.get_custom_rules_path() is None

    # Set custom path to existing file
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(b"[]")
        custom_path = tmp.name

    try:
        monkeypatch.setenv("FUNC_DOCTOR_CUSTOM_RULES", custom_path)
        config = Config()  # Reload to pick up environment variable

        result = config.get_custom_rules_path()
        assert result is not None
        assert result == Path(custom_path)

    finally:
        os.unlink(custom_path)


def test_config_custom_rules_path_nonexistent(monkeypatch: "pytest.MonkeyPatch") -> None:
    """Test custom rules path with nonexistent file."""
    monkeypatch.setenv("FUNC_DOCTOR_CUSTOM_RULES", "/nonexistent/path.json")

    config = Config()

    # Should return None for nonexistent path
    assert config.get_custom_rules_path() is None


def test_config_to_dict() -> None:
    """Test configuration serialization to dictionary."""
    config = Config()
    config.set("test_key", "test_value")

    config_dict = config.to_dict()

    assert isinstance(config_dict, dict)
    assert config_dict["log_level"] == "WARNING"
    assert config_dict["test_key"] == "test_value"


def test_get_config_singleton() -> None:
    """Test that get_config returns the same instance."""
    config1 = get_config()
    config2 = get_config()

    assert config1 is config2


def test_override_config() -> None:
    """Test configuration override functionality."""
    original_log_level = get_config().get("log_level")

    override_config(log_level="DEBUG", test_override="value")

    assert get_config().get("log_level") == "DEBUG"
    assert get_config().get("test_override") == "value"

    # Cleanup
    get_config().set("log_level", original_log_level)


def test_config_invalid_float_environment_value(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setattr(Config, "_defaults", {**Config._defaults, "ratio": 1.5})
    monkeypatch.setenv("FUNC_DOCTOR_RATIO", "not-a-float")

    config = Config()

    assert config.get("ratio") == 1.5
