from rich.style import Style
from rich.text import Text

# Status to icon
STATUS_ICONS: dict[str, str] = {  # nosec B105
    # Unified with README: ✓ (pass), ! (warn), ✗ (fail)
    "pass": "✓",
    "warn": "!",
    "fail": "✗",
    "skip": "–",
}

# Status to styled Text (for section headers)
STATUS_STYLES: dict[str, Style] = {
    "pass": Style(color="green", bold=True),
    "fail": Style(color="red", bold=True),
    "warn": Style(color="yellow", bold=True),
    "skip": Style(color="bright_black", bold=True),
}

# Status to plain color strings (for result details)
DETAIL_COLOR_MAP: dict[str, str] = {  # nosec B105
    "pass": "green",
    "fail": "red",
    "warn": "yellow",
    "skip": "bright_black",
}


def format_status_icon(status: str) -> str:
    """
    Return a simple icon character based on status.

    Args:
        status: Diagnostic status ("pass", "fail", "warn", "skip").

    Returns:
    A string icon such as ✓, !, or ✗.
    """
    return STATUS_ICONS.get(status, "?")


def format_result(status: str) -> Text:
    """
    Return a styled icon Text element based on status.

    Args:
        status: Diagnostic status ("pass", "fail", "warn", "skip").

    Returns:
        A Rich Text object with icon and style for headers.
    """
    style = STATUS_STYLES.get(status, Style(color="white"))
    icon = format_status_icon(status)
    return Text(icon, style=style)


def format_detail(status: str, value: str) -> Text:
    """
    Return a colored Text element based on status and value.

    Args:
        status: Diagnostic status ("pass", "fail", "warn", "skip").
        value: Text to display, typically a description.

    Returns:
        A Rich Text object styled with status color.
    """
    color = DETAIL_COLOR_MAP.get(status, "white")
    return Text(value, style=color)


def format_freshness_line(last_verified: str, source_url: str = "") -> str:
    """Render the Finding Contract v2 freshness line for date/compat findings.

    Args:
        last_verified: The ``YYYY-MM-DD`` date the underlying fact was verified.
        source_url: Optional authoritative source URL for the fact.

    Returns:
        A human-readable ``verified as of YYYY-MM-DD`` string, with the source
        URL appended when available. Returns an empty string when
        ``last_verified`` is missing so callers can skip rendering.
    """
    if not last_verified:
        return ""
    line = f"verified as of {last_verified}"
    if source_url:
        line += f" — {source_url}"
    return line
