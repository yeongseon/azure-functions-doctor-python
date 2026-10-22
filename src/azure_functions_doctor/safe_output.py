"""Deny-by-default rendering for values used in diagnostic messages."""

import re
from typing import Final

SAFE_EXTENSION_VALUES: Final = frozenset({"~1", "~2", "~3", "~4", "1", "2", "3", "4"})


def extension_value(value: str) -> str:
    """Preserve recognized runtime pins; never echo arbitrary setting contents."""
    return value if value in SAFE_EXTENSION_VALUES else "[masked]"


def version_value(value: str) -> str:
    return value if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){0,3}", value) else "[masked]"
