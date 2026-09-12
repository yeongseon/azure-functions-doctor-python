"""Deploy-config ingestion: one authoritative view of the target Azure config.

The doctor's positioning is "will THIS app run on THIS Azure config?". Answering
that requires ingesting the *target* Azure configuration — hosting plan, runtime
name/version, extension version, deployment storage, and key app settings — from
the infrastructure-as-code (bicep / ARM JSON) that already ships in the project,
rather than every rule performing its own ad-hoc regex scan.

This module resolves a single :class:`TargetConfig` object. Every field records
its provenance (:class:`ResolvedField`) and is resolved with a documented
precedence, first match wins:

    CLI explicit override  >  IaC target configuration  >  project/local signal
    >  unknown

When no infrastructure is present the resolution degrades gracefully: every field
is ``unknown`` and no exception is raised, so rules that need a plan can emit a
clear SKIP instead of a false failure.

No runtime network calls are made; only files already in the project are read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Callable, Iterator, Mapping, Optional, Union

from azure_functions_doctor.logging_config import get_logger

logger = get_logger(__name__)

# Provenance markers. IaC values carry the relative infra file path (e.g.
# ``"infra/main.bicep"``) and project/local signals carry ``"local:<filename>"``.
SOURCE_OVERRIDE = "cli-override"
SOURCE_UNKNOWN = "unknown"

# Canonical hosting-plan names (aligned with target_resolver.SUPPORTED_HOSTING_PLANS).
PLAN_FLEX_CONSUMPTION = "flex-consumption"
PLAN_LINUX_CONSUMPTION = "linux-consumption"
PLAN_PREMIUM = "premium"
PLAN_DEDICATED = "dedicated"

# Specificity order used when multiple signals are present in one project: the
# most specific plan wins so a Flex app that also declares a legacy sku block is
# still reported as Flex.
_PLAN_SPECIFICITY = (
    PLAN_FLEX_CONSUMPTION,
    PLAN_LINUX_CONSUMPTION,
    PLAN_PREMIUM,
    PLAN_DEDICATED,
)

_LINUX_FX_PYTHON_RE = re.compile(r"linuxFxVersion['\"]?\s*[:=]\s*['\"]?[Pp]ython\|(\d+\.\d+)")
_EMULATOR_STORAGE = "UseDevelopmentStorage=true"

# SKU signals. Names are matched case-insensitively as whole tokens.
_PREMIUM_SKU_NAMES = {"ep1", "ep2", "ep3"}
_DEDICATED_SKU_NAMES = {
    "b1",
    "b2",
    "b3",
    "s1",
    "s2",
    "s3",
    "p1v2",
    "p2v2",
    "p3v2",
    "p1v3",
    "p2v3",
    "p3v3",
}
_PREMIUM_SKU_TIERS = {"elasticpremium"}
_DEDICATED_SKU_TIERS = {"basic", "standard", "premiumv2", "premiumv3"}
_DYNAMIC_SKU_TIERS = {"dynamic"}


@dataclass(frozen=True)
class ResolvedField:
    """A resolved configuration value together with its provenance."""

    value: Optional[str]
    source: str

    @property
    def is_known(self) -> bool:
        """Return ``True`` when a concrete value was resolved."""
        return self.value is not None


@dataclass(frozen=True)
class TargetConfig:
    """The resolved target Azure configuration, one source of truth for handlers."""

    hosting_plan: ResolvedField
    runtime_name: ResolvedField
    runtime_version: ResolvedField
    extension_version: ResolvedField
    deployment_storage: ResolvedField
    app_settings: dict[str, str] = field(default_factory=dict)
    # Provenance for each ingested app setting: setting name -> declaring file
    # (repo-root-relative), so deploy-rule findings can cite the source (#408).
    app_settings_files: dict[str, str] = field(default_factory=dict)

    @classmethod
    def unknown(cls) -> "TargetConfig":
        """Return a fully-unknown config (used when nothing can be resolved)."""
        blank = ResolvedField(None, SOURCE_UNKNOWN)
        return cls(
            hosting_plan=blank,
            runtime_name=blank,
            runtime_version=blank,
            extension_version=blank,
            deployment_storage=blank,
            app_settings={},
            app_settings_files={},
        )


@dataclass
class _IaCScan:
    """Raw values discovered from a single IaC scan pass, with provenance."""

    hosting_plan: Optional[ResolvedField] = None
    runtime_name: Optional[ResolvedField] = None
    runtime_version: Optional[ResolvedField] = None
    extension_version: Optional[ResolvedField] = None
    deployment_storage: Optional[ResolvedField] = None
    app_settings: dict[str, str] = field(default_factory=dict)
    app_settings_files: dict[str, str] = field(default_factory=dict)


def _shared_traversal() -> Callable[[Path, Union[str, tuple[str, ...], list[str]]], Iterator[Path]]:
    # Imported lazily to avoid an import cycle: the ``handlers`` package
    # re-exports this module's public API from its ``__init__``.
    from azure_functions_doctor.handlers._helpers import iter_project_files

    return iter_project_files


def _read_text(candidate: Path) -> Optional[str]:
    try:
        return candidate.read_text(encoding="utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        logger.debug("Skip unreadable infra file %s", candidate)
        return None


def _rel(candidate: Path, project_path: Path) -> str:
    try:
        return str(candidate.relative_to(project_path))
    except ValueError:  # pragma: no cover - candidate is always under project_path
        return str(candidate)


def _iter_infra_files(project_path: Path) -> list[tuple[Path, str]]:
    """Return ``(path, kind)`` for infra files, kind in ``{"bicep", "json"}``.

    ``local.settings.json`` is deliberately excluded: it is a local developer
    signal, not deployable infrastructure.
    """
    files: list[tuple[Path, str]] = []
    iter_project_files = _shared_traversal()
    for candidate in iter_project_files(project_path, "*.bicep"):
        files.append((candidate, "bicep"))
    for candidate in iter_project_files(project_path, "*.json"):
        if candidate.name == "local.settings.json":
            continue
        files.append((candidate, "json"))
    return files


def _plan_from_sku(name: Optional[str], tier: Optional[str]) -> Optional[str]:
    """Map an Azure sku ``(name, tier)`` pair to a canonical hosting plan."""
    name_l = name.lower() if isinstance(name, str) else ""
    tier_l = tier.lower() if isinstance(tier, str) else ""
    if tier_l in _DYNAMIC_SKU_TIERS or name_l == "y1":
        return PLAN_LINUX_CONSUMPTION
    if tier_l == "flexconsumption" or name_l == "fc1":
        return PLAN_FLEX_CONSUMPTION
    if tier_l in _PREMIUM_SKU_TIERS or name_l in _PREMIUM_SKU_NAMES:
        return PLAN_PREMIUM
    if tier_l in _DEDICATED_SKU_TIERS or name_l in _DEDICATED_SKU_NAMES:
        return PLAN_DEDICATED
    return None


def _more_specific_plan(current: Optional[str], candidate: str) -> str:
    """Return whichever of ``current``/``candidate`` is the more specific plan."""
    if current is None:
        return candidate
    return min(
        (current, candidate),
        key=lambda plan: (
            _PLAN_SPECIFICITY.index(plan) if plan in _PLAN_SPECIFICITY else len(_PLAN_SPECIFICITY)
        ),
    )


def _walk_json(node: object) -> "list[dict[str, object]]":
    """Yield every dict nested anywhere within a parsed JSON structure."""
    found: list[dict[str, object]] = []
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            found.append(current)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found


def _app_settings_from_json(node: object) -> dict[str, str]:
    """Collect ``{name: value}`` app settings from any ``appSettings`` array."""
    settings: dict[str, str] = {}
    for obj in _walk_json(node):
        app_settings = obj.get("appSettings")
        if not isinstance(app_settings, list):
            continue
        for entry in app_settings:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            value = entry.get("value")
            if isinstance(name, str) and isinstance(value, str):
                settings.setdefault(name, value)
    return settings


def _runtime_from_function_app_config(node: object) -> Optional[tuple[str, str]]:
    """Return ``(name, version)`` from a ``functionAppConfig.runtime`` block."""
    for obj in _walk_json(node):
        runtime = obj.get("runtime")
        if isinstance(runtime, dict):
            name = runtime.get("name")
            version = runtime.get("version")
            if isinstance(name, str) and isinstance(version, str):
                return name.lower(), version
    return None


def _deployment_storage_from_json(node: object) -> Optional[str]:
    """Return a Flex ``functionAppConfig.deployment.storage.value`` URL if present."""
    for obj in _walk_json(node):
        deployment = obj.get("deployment")
        if not isinstance(deployment, dict):
            continue
        storage = deployment.get("storage")
        if not isinstance(storage, dict):
            continue
        value = storage.get("value")
        if isinstance(value, str):
            return value
    return None


def flex_deployment_storage_shape(project_path: Path) -> Optional[dict[str, object]]:
    """Return the Flex ``functionAppConfig.deployment.storage`` object from infra.

    Scans deployable infra JSON files for a ``deployment.storage`` block and
    returns the first one found, or ``None`` when none is declared. Raw ``.bicep``
    files are not statically parsed for nested shapes, so a project expressed only
    in bicep yields ``None`` (the deployment-storage check then skips gracefully).
    ``local.settings.json`` is excluded by :func:`_iter_infra_files`.
    """
    for candidate, kind in _iter_infra_files(project_path):
        if kind != "json":
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError, OSError):
            continue
        for obj in _walk_json(data):
            deployment = obj.get("deployment")
            if not isinstance(deployment, dict):
                continue
            storage = deployment.get("storage")
            if isinstance(storage, dict):
                return storage
    return None


def _has_function_app_config(node: object) -> bool:
    return any("functionAppConfig" in obj for obj in _walk_json(node))


def _plan_from_json(node: object) -> Optional[str]:
    plan: Optional[str] = None
    if _has_function_app_config(node):
        plan = _more_specific_plan(plan, PLAN_FLEX_CONSUMPTION)
    for obj in _walk_json(node):
        sku = obj.get("sku")
        if isinstance(sku, dict):
            candidate = _plan_from_sku(
                sku.get("name") if isinstance(sku.get("name"), str) else None,
                sku.get("tier") if isinstance(sku.get("tier"), str) else None,
            )
            if candidate is not None:
                plan = _more_specific_plan(plan, candidate)
    return plan


def _scan_json_file(text: str, rel: str, scan: _IaCScan) -> None:
    try:
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError):
        logger.debug("Skip non-JSON / malformed infra file %s", rel)
        return

    plan = _plan_from_json(data)
    if plan is not None and scan.hosting_plan is None:
        scan.hosting_plan = ResolvedField(plan, rel)

    runtime = _runtime_from_function_app_config(data)
    if runtime is not None:
        if scan.runtime_name is None:
            scan.runtime_name = ResolvedField(runtime[0], rel)
        if scan.runtime_version is None:
            scan.runtime_version = ResolvedField(runtime[1], rel)

    settings = _app_settings_from_json(data)
    for name, value in settings.items():
        scan.app_settings.setdefault(name, value)
        scan.app_settings_files.setdefault(name, rel)
    ext = settings.get("FUNCTIONS_EXTENSION_VERSION")
    if ext is not None and scan.extension_version is None:
        scan.extension_version = ResolvedField(ext, rel)

    storage = _deployment_storage_from_json(data)
    if storage is None:
        storage = settings.get("AzureWebJobsStorage")
    if storage is not None and scan.deployment_storage is None:
        scan.deployment_storage = ResolvedField(storage, rel)


def _scan_bicep_file(text: str, rel: str, scan: _IaCScan) -> None:
    if scan.hosting_plan is None and "functionAppConfig" in text:
        scan.hosting_plan = ResolvedField(PLAN_FLEX_CONSUMPTION, rel)
    match = _LINUX_FX_PYTHON_RE.search(text)
    if match is not None:
        if scan.runtime_name is None:
            scan.runtime_name = ResolvedField("python", rel)
        if scan.runtime_version is None:
            scan.runtime_version = ResolvedField(match.group(1), rel)
    for name, value in re.findall(r"name:\s*'([^']+)'\s*\n?\s*value:\s*'([^']*)'", text):
        scan.app_settings.setdefault(name, value)
        scan.app_settings_files.setdefault(name, rel)
    ext = scan.app_settings.get("FUNCTIONS_EXTENSION_VERSION")
    if ext is not None and scan.extension_version is None:
        scan.extension_version = ResolvedField(ext, rel)
    storage = scan.app_settings.get("AzureWebJobsStorage")
    if storage is None and _EMULATOR_STORAGE in text and "AzureWebJobsStorage" in text:
        storage = _EMULATOR_STORAGE
    if storage is not None and scan.deployment_storage is None:
        scan.deployment_storage = ResolvedField(storage, rel)


def _scan_iac(project_path: Path) -> _IaCScan:
    scan = _IaCScan()
    for candidate, kind in _iter_infra_files(project_path):
        text = _read_text(candidate)
        if text is None:
            continue
        rel = _rel(candidate, project_path)
        if kind == "json":
            _scan_json_file(text, rel, scan)
        else:
            _scan_bicep_file(text, rel, scan)
    return scan


def _local_signals(project_path: Path) -> _IaCScan:
    """Resolve project/local signals (lowest precedence above ``unknown``)."""
    signals = _IaCScan()
    settings_path = project_path / "local.settings.json"
    text = _read_text(settings_path)
    if text is None:
        return signals
    try:
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError):
        return signals
    values = data.get("Values") if isinstance(data, dict) else None
    if not isinstance(values, dict):
        return signals
    source = "local:local.settings.json"
    ext = values.get("FUNCTIONS_EXTENSION_VERSION")
    if isinstance(ext, str):
        signals.extension_version = ResolvedField(ext, source)
    storage = values.get("AzureWebJobsStorage")
    if isinstance(storage, str):
        signals.deployment_storage = ResolvedField(storage, source)
    return signals


def local_settings_values(project_path: Path) -> dict[str, str]:
    """Return the string entries of ``local.settings.json`` ``Values`` (empty if absent).

    Only string-valued entries are returned; non-string values are ignored. This is
    read directly (not through the precedence-based :func:`resolve_target_config`
    ingestion) so the binding-connection resolution check (#352) can resolve
    connection names against locally configured settings without changing what
    :class:`TargetConfig.app_settings` exposes to other checks.
    """
    text = _read_text(project_path / "local.settings.json")
    if text is None:
        return {}
    try:
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError):
        return {}
    values = data.get("Values") if isinstance(data, dict) else None
    if not isinstance(values, dict):
        return {}
    return {
        key: value
        for key, value in values.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _resolve_field(
    override: Optional[str],
    iac: Optional[ResolvedField],
    local: Optional[ResolvedField],
) -> ResolvedField:
    """Apply precedence override > IaC > local signal > unknown for one field."""
    if override is not None:
        return ResolvedField(override, SOURCE_OVERRIDE)
    if iac is not None:
        return iac
    if local is not None:
        return local
    return ResolvedField(None, SOURCE_UNKNOWN)


def resolve_target_config(
    project_path: Path,
    overrides: Optional[Mapping[str, Optional[str]]] = None,
) -> TargetConfig:
    """Resolve the target Azure configuration for ``project_path``.

    Args:
        project_path: Root of the project under diagnosis.
        overrides: Optional CLI overrides. Recognized keys are ``"hosting_plan"``
            and ``"runtime_version"``; a non-``None`` value takes precedence over
            any IaC or local signal for that field.

    Returns:
        A :class:`TargetConfig` where every field records its provenance. When no
        infrastructure or signal is found, all fields are ``unknown``.
    """
    overrides = overrides or {}
    iac = _scan_iac(project_path)
    local = _local_signals(project_path)

    app_settings = dict(local.app_settings)
    app_settings.update(iac.app_settings)

    return TargetConfig(
        hosting_plan=_resolve_field(
            overrides.get("hosting_plan"), iac.hosting_plan, local.hosting_plan
        ),
        runtime_name=_resolve_field(None, iac.runtime_name, local.runtime_name),
        runtime_version=_resolve_field(
            overrides.get("runtime_version"), iac.runtime_version, local.runtime_version
        ),
        extension_version=_resolve_field(None, iac.extension_version, local.extension_version),
        deployment_storage=_resolve_field(None, iac.deployment_storage, local.deployment_storage),
        app_settings=app_settings,
        app_settings_files=dict(iac.app_settings_files),
    )
