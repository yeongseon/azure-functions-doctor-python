"""Version-controlled Azure Functions compatibility catalog.

This module loads a version-controlled snapshot of Azure Functions support-matrix
facts (Python version lifecycle, hosting-plan Python caps, runtime lifecycle) from
``assets/compatibility/catalog.json``. The catalog is the single, auditable source
of truth for every date/compatibility rule: each fact carries a source URL and a
``last_verified`` date, and lifecycle dates are tagged with the *precision* at which
Microsoft publishes them (day / month / year) so the tool never renders a more
precise date than the source provides.

No runtime network calls are made; the catalog ships with the package.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
import importlib.resources
import json
from typing import Literal, Optional

from azure_functions_doctor.logging_config import get_logger

logger = get_logger(__name__)

# Number of days after which the shipped catalog is considered stale. Staleness is
# a property of the catalog snapshot itself, reported separately from any finding
# severity: a stale catalog emits its own ``catalog_stale`` warning, never an error
# on the diagnosed project.
CATALOG_STALENESS_THRESHOLD_DAYS = 180

Precision = Literal["day", "month", "year"]

_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _parse_major_minor(version: str) -> Optional[tuple[int, int]]:
    """Return the ``(major, minor)`` pair for a ``"3.12"``-style string."""
    parts = version.split(".")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


@dataclass(frozen=True)
class SupportEnd:
    """A lifecycle end date modelled at the precision the source publishes.

    ``value`` is ``YYYY-MM-DD`` for day precision, ``YYYY-MM`` for month precision,
    and ``YYYY`` for year precision. ``render`` formats the value at that precision
    and never synthesizes finer detail than the source provides.
    """

    value: str
    precision: Precision

    def render(self) -> str:
        """Render the date at its stated precision (e.g. ``"October 2026"``)."""
        parts = self.value.split("-")
        try:
            if self.precision == "day" and len(parts) == 3:
                validated = date(int(parts[0]), int(parts[1]), int(parts[2]))
                return f"{_MONTH_NAMES[validated.month - 1]} {validated.day}, {validated.year}"
            if self.precision == "month" and len(parts) >= 2:
                year, month = int(parts[0]), int(parts[1])
                date(year, month, 1)  # validate month is in 1..12
                return f"{_MONTH_NAMES[month - 1]} {year}"
            if self.precision == "year":
                return str(int(parts[0]))
        except (ValueError, IndexError):
            logger.warning(
                "Malformed support_end value %r for precision %s", self.value, self.precision
            )
        return self.value

    def end_date(self) -> Optional[date]:
        """Return the last calendar day covered by this support-end value.

        For month precision the last day of the month is used, and for year
        precision December 31, so date comparisons never treat a coarse value as
        expiring earlier than the source guarantees. Malformed values yield
        ``None``.
        """
        parts = self.value.split("-")
        try:
            if self.precision == "day" and len(parts) == 3:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            if self.precision == "month" and len(parts) >= 2:
                year, month = int(parts[0]), int(parts[1])
                last_day = calendar.monthrange(year, month)[1]
                return date(year, month, last_day)
            if self.precision == "year":
                return date(int(parts[0]), 12, 31)
        except (ValueError, IndexError):
            logger.warning(
                "Malformed support_end value %r for precision %s", self.value, self.precision
            )
        return None


@dataclass(frozen=True)
class Fact:
    """A single catalog fact with source and freshness metadata."""

    fact_id: str
    category: str
    applies_to: dict[str, str]
    source_url: str
    last_verified: str
    verification_notes: str
    status: Optional[str] = None
    support_end: Optional[SupportEnd] = None
    max_python: Optional[str] = None
    supersedes: Optional[str] = None

    def effective_status(self, today: Optional[date] = None) -> Optional[str]:
        """Return the status reconciled with ``today`` and ``support_end``.

        The stored ``status`` is the source-verified baseline. When an
        end-of-support date is known this reconciles it with the calendar so a
        future end date is never reported as ``unsupported`` and a past end date
        is never reported as still supported. The transition is deterministic and
        self-correcting as time passes, without re-verifying the catalog.
        """
        if self.support_end is None:
            return self.status
        eos = self.support_end.end_date()
        if eos is None:
            return self.status
        current = today if today is not None else date.today()
        if current > eos:
            return "unsupported"
        if self.status == "unsupported":
            return "retiring"
        return self.status


@dataclass(frozen=True)
class Freshness:
    """Freshness state of the catalog snapshot, independent of any finding."""

    last_verified: str
    age_days: int
    is_stale: bool
    threshold_days: int


@dataclass(frozen=True)
class Catalog:
    """Parsed, in-memory view of the compatibility catalog."""

    catalog_version: str
    last_verified: str
    sources: dict[str, str]
    facts: tuple[Fact, ...]

    def get_fact(self, fact_id: str) -> Optional[Fact]:
        """Return the fact with ``fact_id`` or ``None``."""
        for fact in self.facts:
            if fact.fact_id == fact_id:
                return fact
        return None

    def facts_by_category(self, category: str) -> tuple[Fact, ...]:
        """Return all facts in ``category`` in catalog order."""
        return tuple(fact for fact in self.facts if fact.category == category)

    def known_python_versions(self) -> tuple[str, ...]:
        """Return every Python ``major.minor`` in the catalog, sorted ascending."""
        versions = [
            fact.applies_to["python"]
            for fact in self.facts_by_category("python_runtime_lifecycle")
            if "python" in fact.applies_to
        ]
        return tuple(sorted(versions, key=lambda v: _parse_major_minor(v) or (0, 0)))

    def supported_python_versions(self, as_of: Optional[date] = None) -> tuple[str, ...]:
        """Return Python versions still supported as of ``as_of`` (default today).

        A version is supported unless its effective status (baseline status
        reconciled with its end-of-support date) is ``"unsupported"``.
        """
        versions = [
            fact.applies_to["python"]
            for fact in self.facts_by_category("python_runtime_lifecycle")
            if "python" in fact.applies_to and fact.effective_status(as_of) != "unsupported"
        ]
        return tuple(sorted(versions, key=lambda v: _parse_major_minor(v) or (0, 0)))

    def python_versions(self) -> tuple[str, ...]:
        """Backward-compatible alias for :meth:`known_python_versions`."""
        return self.known_python_versions()

    def python_lifecycle_fact(self, version: str) -> Optional[Fact]:
        """Return the ``python_runtime_lifecycle`` fact for a Python ``version``."""
        target = _parse_major_minor(version)
        if target is None:
            return None
        for fact in self.facts_by_category("python_runtime_lifecycle"):
            applies = fact.applies_to.get("python")
            if applies is not None and _parse_major_minor(applies) == target:
                return fact
        return None

    def python_eos(self, version: str) -> Optional[SupportEnd]:
        """Return the published end-of-support date for a Python ``version``."""
        fact = self.python_lifecycle_fact(version)
        return fact.support_end if fact is not None else None

    def functions_runtime_fact(self, runtime: str) -> Optional[Fact]:
        """Return the plan-agnostic ``functions_runtime_lifecycle`` fact for a
        runtime like ``"4.x"`` (the fact whose ``applies_to`` has no
        ``hosting_plan`` qualifier). Returns ``None`` when unknown.
        """
        for fact in self.facts_by_category("functions_runtime_lifecycle"):
            if (
                fact.applies_to.get("functions_runtime") == runtime
                and "hosting_plan" not in fact.applies_to
            ):
                return fact
        return None

    def functions_runtime_plan_fact(self, runtime: str, hosting_plan: str) -> Optional[Fact]:
        """Return a plan-specific ``functions_runtime_lifecycle`` fact (e.g. the
        v3-on-Linux-Consumption stop-running fact) or ``None``.
        """
        for fact in self.facts_by_category("functions_runtime_lifecycle"):
            if (
                fact.applies_to.get("functions_runtime") == runtime
                and fact.applies_to.get("hosting_plan") == hosting_plan
            ):
                return fact
        return None

    def hosting_plan_lifecycle_fact(self, hosting_plan: str) -> Optional[Fact]:
        """Return the ``hosting_plan_lifecycle`` fact for ``hosting_plan`` or
        ``None`` when the plan has no published retirement.
        """
        for fact in self.facts_by_category("hosting_plan_lifecycle"):
            if fact.applies_to.get("hosting_plan") == hosting_plan:
                return fact
        return None

    def flex_deprecated_settings_fact(self) -> Optional[Fact]:
        """Return the ``flex_deprecated_settings`` catalog fact or ``None``.

        This single fact carries the source URL and freshness metadata for the
        Flex Consumption deprecated-app-settings check (issue #350); the list of
        deprecated settings itself lives in the rule handler.
        """
        facts = self.facts_by_category("flex_deprecated_settings")
        return facts[0] if facts else None

    def hosting_plan_matrix(self) -> dict[str, tuple[str, ...]]:
        """Reconstruct the per-plan supported-Python matrix from the catalog.

        Each plan's allow-list is the globally supported Python set filtered by that
        plan's ``max_python`` cap (plans without a cap track the full set).
        """
        supported = self.supported_python_versions()
        matrix: dict[str, tuple[str, ...]] = {}
        for fact in self.facts_by_category("hosting_plan_python_cap"):
            plan = fact.applies_to.get("hosting_plan")
            if plan is None:
                continue
            cap = _parse_major_minor(fact.max_python) if fact.max_python else None
            if cap is None:
                matrix[plan] = supported
            else:
                matrix[plan] = tuple(
                    v for v in supported if (_parse_major_minor(v) or (0, 0)) <= cap
                )
        return matrix

    def freshness(self, today: Optional[date] = None) -> Freshness:
        """Return the catalog's freshness state relative to ``today``."""
        current = today if today is not None else date.today()
        try:
            verified = date.fromisoformat(self.last_verified)
            age_days = (current - verified).days
        except ValueError:
            logger.warning("Malformed catalog last_verified %r", self.last_verified)
            age_days = 0
        return Freshness(
            last_verified=self.last_verified,
            age_days=age_days,
            is_stale=age_days > CATALOG_STALENESS_THRESHOLD_DAYS,
            threshold_days=CATALOG_STALENESS_THRESHOLD_DAYS,
        )


def _parse_support_end(raw: Optional[dict[str, object]]) -> Optional[SupportEnd]:
    if raw is None:
        return None
    value = raw.get("value")
    precision = raw.get("precision")
    if not isinstance(value, str) or precision not in ("day", "month", "year"):
        return None
    return SupportEnd(value=value, precision=precision)


def _as_str(value: object, default: str = "") -> str:
    """Return ``value`` when it is a string, else ``default``.

    Unlike ``str(value)`` this never turns an explicit JSON ``null`` into the
    literal ``"None"``, preserving the module's tolerant-parsing contract.
    """
    return value if isinstance(value, str) else default


def _parse_fact(raw: dict[str, object]) -> Fact:
    support_end_raw = raw.get("support_end")
    support_end = _parse_support_end(support_end_raw if isinstance(support_end_raw, dict) else None)
    applies_raw = raw.get("applies_to")
    applies_to = (
        {str(k): str(v) for k, v in applies_raw.items()} if isinstance(applies_raw, dict) else {}
    )
    max_python = raw.get("max_python")
    supersedes = raw.get("supersedes")
    status = raw.get("status")
    return Fact(
        fact_id=_as_str(raw.get("fact_id")),
        category=_as_str(raw.get("category")),
        applies_to=applies_to,
        source_url=_as_str(raw.get("source_url")),
        last_verified=_as_str(raw.get("last_verified")),
        verification_notes=_as_str(raw.get("verification_notes")),
        status=str(status) if isinstance(status, str) else None,
        support_end=support_end,
        max_python=str(max_python) if isinstance(max_python, str) else None,
        supersedes=str(supersedes) if isinstance(supersedes, str) else None,
    )


def _build_catalog(raw: dict[str, object]) -> Catalog:
    sources_raw = raw.get("sources")
    sources = (
        {str(k): str(v) for k, v in sources_raw.items()} if isinstance(sources_raw, dict) else {}
    )
    facts_raw = raw.get("facts")
    facts = (
        tuple(_parse_fact(item) for item in facts_raw if isinstance(item, dict))
        if isinstance(facts_raw, list)
        else ()
    )
    return Catalog(
        catalog_version=str(raw.get("catalog_version", "")),
        last_verified=str(raw.get("last_verified", "")),
        sources=sources,
        facts=facts,
    )


_CATALOG_CACHE: Optional[Catalog] = None


def load_catalog() -> Catalog:
    """Load and cache the version-controlled compatibility catalog.

    The catalog ships with the package under ``assets/compatibility/catalog.json``;
    no network calls are made.
    """
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    catalog_path = importlib.resources.files("azure_functions_doctor.assets").joinpath(
        "compatibility/catalog.json"
    )
    try:
        with catalog_path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - packaging safeguard
        logger.error("compatibility catalog.json not found")
        raise RuntimeError("compatibility catalog.json not found") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - packaging safeguard
        logger.error("Invalid JSON in catalog.json: %s", exc)
        raise RuntimeError(f"Failed to parse catalog.json: {exc}") from exc

    if not isinstance(raw, dict):
        logger.error("catalog.json root is not a JSON object")
        raise RuntimeError("catalog.json root must be a JSON object")

    _CATALOG_CACHE = _build_catalog(raw)
    return _CATALOG_CACHE
