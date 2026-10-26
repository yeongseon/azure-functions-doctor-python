import ast
from unittest.mock import patch

import pytest

from azure_functions_doctor.source_cache import parse_source, source_cache


def test_repeated_source_parses_once_inside_phase() -> None:
    with patch("ast.parse", wraps=ast.parse) as parser, source_cache():
        first = parse_source("value = 1")
        second = parse_source("value = 1")
    assert first is second
    assert parser.call_count == 1


def test_phase_exit_and_nested_phase_restore_isolation() -> None:
    with source_cache():
        outer = parse_source("value = 1")
        with source_cache():
            inner = parse_source("value = 1")
        assert parse_source("value = 1") is outer
    assert parse_source("value = 1") is not outer
    assert inner is not outer


def test_parse_failure_does_not_poison_valid_sources() -> None:
    with source_cache():
        with pytest.raises(SyntaxError):
            parse_source("def broken(")
        assert isinstance(parse_source("value = 2"), ast.Module)


def test_cache_bound_falls_back_without_changing_results() -> None:
    with source_cache():
        for index in range(128):
            parse_source(f"value = {index}")
        first = parse_source("overflow = True")
        second = parse_source("overflow = True")
    assert first is not second
    assert ast.dump(first) == ast.dump(second)
