"""Runtime-lifecycle handlers and evaluators (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

from datetime import date
from pathlib import Path
import re
from typing import Optional

from azure_functions_doctor.compatibility import Catalog, Fact, load_catalog
from azure_functions_doctor.handlers._helpers import (
    HandlerResult,
    Rule,
    RuleContext,
    _create_result,
    _rule_handler,
)
from azure_functions_doctor.target_resolver import (
    resolve_python_target,
)

# Issue #343: a Python runtime is flagged "retiring soon" (WARN) when its
# published Azure Functions end-of-support date falls within this many days of
# today. Beyond the window the runtime is "supported" (PASS); once the date has
# passed it is "unsupported" (FAIL). Comparison uses the last calendar day the
# source guarantees (month/year precision is widened, never narrowed), so the
# tool never asserts a finer date than Microsoft publishes.
PYTHON_RETIRING_SOON_WINDOW_DAYS = 180


def _evaluate_python_lifecycle(
    version: str,
    *,
    today: date,
    catalog: Optional[Catalog] = None,
) -> HandlerResult:
    """Classify a Python ``version`` against its catalog end-of-support date.

    Returns a :class:`HandlerResult` whose ``status``/``severity``/``gate`` encode
    one of three deterministic states:

    * **supported** -> ``pass``
    * **retiring soon** (within :data:`PYTHON_RETIRING_SOON_WINDOW_DAYS`) ->
      failing status refined to ``warning`` severity, non-gating
    * **unsupported** (past end-of-support) -> failing status refined to
      ``error`` severity, gating

    Dates are rendered at the precision the catalog publishes (e.g.
    ``"October 2026"``); no day-level countdown is synthesized. Auditable
    evidence (source URL, ``last_verified``, ``catalog_version``) is attached so
    the finding is offline-verifiable per the Finding Contract v2 (issue #348).
    """
    cat = load_catalog() if catalog is None else catalog
    fact = cat.python_lifecycle_fact(version)
    if fact is None or fact.support_end is None:
        # No lifecycle data for this version (e.g. a version outside the
        # supported band); check_python_version owns that failure, so stay quiet.
        return _create_result("pass", f"Python {version}: no catalog lifecycle data")

    eos = fact.support_end
    rendered = eos.render()
    end = eos.end_date()
    last_verified = fact.last_verified or cat.last_verified

    # Recommendation is derived from the catalog (single source of truth for
    # Azure version knowledge), never hardcoded in this handler: point at the
    # newest still-supported Python so the advice stays correct as the
    # catalog rolls forward.
    supported = cat.supported_python_versions(as_of=today)
    recommended = supported[-1] if supported else None
    target_hint = f" (e.g. {recommended})" if recommended else ""

    if end is not None and today > end:
        status, severity, gate = "fail", "error", True
        detail = (
            f"Python {version} is past Azure Functions end-of-support "
            f"(ended {rendered}); upgrade to a newer supported Python{target_hint}."
        )
    elif end is not None and (end - today).days <= PYTHON_RETIRING_SOON_WINDOW_DAYS:
        status, severity, gate = "fail", "warning", False
        detail = (
            f"Python {version} support is expected to end in {rendered}; "
            f"plan an upgrade to a newer supported Python{target_hint} before then."
        )
    else:
        status, severity, gate = "pass", "info", False
        detail = (
            f"Python {version} is supported; Azure Functions support is "
            f"expected to end in {rendered}."
        )

    result = _create_result(status, detail)
    result["severity"] = severity
    result["gate"] = gate
    result["evidence"] = detail
    result["expected"] = "A supported Azure Functions Python runtime"
    result["actual"] = f"Python {version} (support ends {rendered})"
    if fact.source_url:
        result["source_url"] = fact.source_url
    if last_verified:
        result["last_verified"] = last_verified
    if cat.catalog_version:
        result["catalog_version"] = cat.catalog_version
    return result


# Issue #344: the only GA Azure Functions runtime major version. v1 is a legacy
# runtime (C#/.NET Framework only, incompatible with Python) and v2/v3 are out of
# support.
FUNCTIONS_RUNTIME_CURRENT = "4.x"

# Hosting-plan retirement reuses the Python runtime "retiring soon" window: a
# scheduled retirement WARNs inside the window, is an informational note beyond
# it, and FAILs once the date has passed.
HOSTING_PLAN_RETIRING_SOON_WINDOW_DAYS = 180


def _normalize_functions_runtime(ext_version: Optional[str]) -> Optional[str]:
    """Map a ``FUNCTIONS_EXTENSION_VERSION`` value to a ``"N.x"`` runtime key.

    Accepts the pinned forms Azure uses (``"~4"``, ``"4"``, ``"4.0.1"``) and
    returns ``"4.x"``. Returns ``None`` when no major version can be parsed.
    """
    if not ext_version:
        return None
    cleaned = ext_version.strip().lstrip("~")
    match = re.match(r"(\d+)", cleaned)
    if match is None:
        return None
    return f"{int(match.group(1))}.x"


def _attach_catalog_evidence(
    result: HandlerResult,
    fact: Fact,
    catalog: Catalog,
    *,
    detail: str,
    expected: str,
    actual: str,
) -> None:
    """Attach Finding Contract v2 evidence (issue #348) sourced from a catalog fact."""
    result["evidence"] = detail
    result["expected"] = expected
    result["actual"] = actual
    if fact.source_url:
        result["source_url"] = fact.source_url
    last_verified = fact.last_verified or catalog.last_verified
    if last_verified:
        result["last_verified"] = last_verified
    if catalog.catalog_version:
        result["catalog_version"] = catalog.catalog_version


def _evaluate_functions_runtime_lifecycle(
    runtime_version: Optional[str],
    hosting_plan: Optional[str],
    *,
    today: date,
    catalog: Optional[Catalog] = None,
) -> HandlerResult:
    """Classify the Azure Functions runtime major version for a Python app.

    Compatibility is judged first (issue #344): runtime v1 is a legacy runtime
    for C#/.NET Framework apps and is incompatible with a Python target
    regardless of its end-of-support date, so it FAILs on a compatibility basis
    with an added lifecycle note. v2/v3 are out of support (FAIL); v3 on Linux
    Consumption stops running on a published date (emphasised FAIL). v4 is the
    current GA runtime (PASS). An undeterminable runtime SKIPs.

    ``today`` is accepted for deterministic testing though the current states are
    compatibility-driven rather than window-driven.
    """
    cat = load_catalog() if catalog is None else catalog
    runtime = _normalize_functions_runtime(runtime_version)
    if runtime is None:
        return _create_result(
            "skip",
            "Azure Functions runtime version could not be determined from infra "
            "or app settings; check skipped.",
        )

    if runtime == FUNCTIONS_RUNTIME_CURRENT:
        detail = "Azure Functions runtime v4 is the current GA runtime."
        result = _create_result("pass", detail)
        result["severity"] = "info"
        result["gate"] = False
        fact = cat.functions_runtime_fact(runtime)
        if fact is not None:
            _attach_catalog_evidence(
                result,
                fact,
                cat,
                detail=detail,
                expected="Azure Functions runtime v4 (~4)",
                actual="Azure Functions runtime v4",
            )
        return result

    if runtime == "1.x":
        fact = cat.functions_runtime_fact(runtime)
        note = ""
        if fact is not None and fact.support_end is not None:
            note = f" Runtime v1 support ends {fact.support_end.render()}."
        detail = (
            "Azure Functions runtime v1 is not compatible with Python "
            "(v1 supports only C#/.NET Framework apps); migrate to runtime v4." + note
        )
        result = _create_result("fail", detail)
        result["severity"] = "error"
        result["gate"] = True
        if fact is not None:
            _attach_catalog_evidence(
                result,
                fact,
                cat,
                detail=detail,
                expected="Azure Functions runtime v4 (~4) for a Python app",
                actual="Azure Functions runtime v1 (incompatible with Python)",
            )
        return result

    if runtime == "3.x" and hosting_plan == "linux-consumption":
        fact = cat.functions_runtime_plan_fact(runtime, hosting_plan)
        if fact is not None:
            stop = (
                fact.support_end.render() if fact.support_end is not None else "the published date"
            )
            detail = (
                "Azure Functions runtime v3 apps on Linux Consumption stop "
                f"running after {stop}; migrate to runtime v4."
            )
            result = _create_result("fail", detail)
            result["severity"] = "error"
            result["gate"] = True
            _attach_catalog_evidence(
                result,
                fact,
                cat,
                detail=detail,
                expected="Azure Functions runtime v4 (~4)",
                actual="Azure Functions runtime v3 on Linux Consumption",
            )
            return result

    fact = cat.functions_runtime_fact(runtime)
    ended = ""
    if fact is not None and fact.support_end is not None:
        ended = f" (ended {fact.support_end.render()})"
    major = runtime.split(".")[0]
    detail = f"Azure Functions runtime v{major} is out of support{ended}; migrate to runtime v4."
    result = _create_result("fail", detail)
    result["severity"] = "error"
    result["gate"] = True
    if fact is not None:
        _attach_catalog_evidence(
            result,
            fact,
            cat,
            detail=detail,
            expected="Azure Functions runtime v4 (~4)",
            actual=f"Azure Functions runtime v{major}",
        )
    return result


def _evaluate_hosting_plan_lifecycle(
    hosting_plan: Optional[str],
    *,
    today: date,
    catalog: Optional[Catalog] = None,
) -> HandlerResult:
    """Classify a hosting plan against its published retirement date (issue #344).

    Linux Consumption is retiring on a published date: informational while the
    date is far off, a WARN inside the retiring-soon window, and a FAIL once the
    date has passed. Plans with no published retirement PASS. An undeterminable
    plan SKIPs.
    """
    cat = load_catalog() if catalog is None else catalog
    if not hosting_plan:
        return _create_result(
            "skip",
            "Hosting plan could not be determined from infra config; check skipped.",
        )

    fact = cat.hosting_plan_lifecycle_fact(hosting_plan)
    if fact is None or fact.support_end is None:
        return _create_result(
            "pass",
            f"Hosting plan '{hosting_plan}' has no published retirement date.",
        )

    rendered = fact.support_end.render()
    end = fact.support_end.end_date()
    if end is not None and today > end:
        status, severity, gate = "fail", "error", True
        detail = (
            f"The '{hosting_plan}' hosting plan retired on {rendered}; migrate to Flex Consumption."
        )
    elif end is not None and (end - today).days <= HOSTING_PLAN_RETIRING_SOON_WINDOW_DAYS:
        status, severity, gate = "fail", "warning", False
        detail = (
            f"The '{hosting_plan}' hosting plan is retiring on {rendered}; "
            "migrate to Flex Consumption before then."
        )
    else:
        status, severity, gate = "pass", "info", False
        detail = (
            f"The '{hosting_plan}' hosting plan is supported; it retires on "
            f"{rendered}. Consider Flex Consumption for new workloads."
        )

    result = _create_result(status, detail)
    result["severity"] = severity
    result["gate"] = gate
    _attach_catalog_evidence(
        result,
        fact,
        cat,
        detail=detail,
        expected="A hosting plan with no near-term retirement (e.g. Flex Consumption)",
        actual=f"{hosting_plan} (retires {rendered})",
    )
    return result


# Issue #345: Flex Consumption declares its runtime under
# ``functionAppConfig.runtime`` (name/version) and ignores ``linuxFxVersion``.
# The canonical plan name matches deploy_config.PLAN_FLEX_CONSUMPTION.


class RuntimeHandlers:
    """Runtime-lifecycle handlers and evaluators.

    Python end-of-support, Functions runtime (~4), hosting-plan retirement.
    """

    @_rule_handler
    def _handle_python_runtime_lifecycle(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Flag a target Python runtime that is retiring soon or unsupported.

        Reads end-of-support dates from the compatibility catalog (never
        hardcoded) and renders them at the catalog's published precision, so a
        month-precision source yields e.g. "October 2026" with no invented day
        or countdown.
        """
        target_python = context.get("target_python") if context is not None else None
        version, _source = resolve_python_target(path, override=target_python)
        return _evaluate_python_lifecycle(version, today=date.today())

    @_rule_handler
    def _handle_functions_runtime_lifecycle(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check the Azure Functions runtime major version for a Python app.

        The runtime major version is read from the resolved target config's
        ``FUNCTIONS_EXTENSION_VERSION`` (e.g. ``~4``); v1 is judged incompatible
        with Python first, with lifecycle dates sourced from the catalog.
        """
        target_config = context.get("target_config") if context is not None else None
        runtime_version: Optional[str] = None
        hosting_plan: Optional[str] = None
        if target_config is not None:
            runtime_version = target_config.extension_version.value
            hosting_plan = target_config.hosting_plan.value
        result = _evaluate_functions_runtime_lifecycle(
            runtime_version, hosting_plan, today=date.today()
        )
        if result["status"] not in ("pass", "skip") and target_config is not None:
            source = target_config.extension_version.source
            if source and not source.startswith("unknown"):
                result["file"] = source.removeprefix("local:")
        return result

    @_rule_handler
    def _handle_hosting_plan_lifecycle(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check the resolved hosting plan against its published retirement date."""
        target_config = context.get("target_config") if context is not None else None
        hosting_plan = target_config.hosting_plan.value if target_config is not None else None
        result = _evaluate_hosting_plan_lifecycle(hosting_plan, today=date.today())
        if result["status"] not in ("pass", "skip") and target_config is not None:
            source = target_config.hosting_plan.source
            if source and not source.startswith("unknown"):
                result["file"] = source.removeprefix("local:")
        return result
