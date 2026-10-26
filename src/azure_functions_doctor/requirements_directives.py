"""Parse local pip include directives consistently before deciding whether to follow them."""

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class IncludeDirective:
    reference: str
    constraint: bool


def parse_include_directive(line: str) -> IncludeDirective | None:
    match = re.match(
        r"^(?:-(?P<short>[rc])|--(?P<long>requirement|constraint)(?:\s+|=))(?P<value>.+)$",
        line.removeprefix("\ufeff").strip(),
    )
    if match is None:
        return None
    reference = match.group("value").split(" #", 1)[0].strip().strip("'\"")
    if not reference:
        return None
    return IncludeDirective(
        reference, match.group("short") == "c" or match.group("long") == "constraint"
    )
