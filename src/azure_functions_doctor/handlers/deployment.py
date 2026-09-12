"""Deployment-correctness handlers and evaluators (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

import json
from pathlib import Path
import re
from typing import Optional

from azure_functions_doctor.compatibility import Catalog, load_catalog
from azure_functions_doctor.deploy_config import (
    flex_deployment_storage_shape,
    local_settings_values,
)
from azure_functions_doctor.handlers._helpers import (
    _HOST_JSON_MISSING,
    HandlerResult,
    Rule,
    RuleContext,
    _create_result,
    _handle_specific_exceptions,
    _resolve_host_json_path,
    _rule_handler,
    iter_project_files,
)
from azure_functions_doctor.handlers.runtime import _attach_catalog_evidence
from azure_functions_doctor.target_resolver import (
    PYTHON_HOSTING_PLAN_MATRIX,
    SUPPORTED_PYTHON_VERSIONS,
    is_supported_python_for_plan,
    is_supported_python_target,
)

FLEX_CONSUMPTION_PLAN = "flex-consumption"

_LINUX_FX_KEY_RE = re.compile(r"linuxFxVersion", re.IGNORECASE)


def _infra_declares_linux_fx_version(path: Path) -> bool:
    """Return ``True`` when any infra file declares a ``linuxFxVersion`` key.

    Flex Consumption ignores ``linuxFxVersion``; its presence on a Flex app is a
    misconfiguration worth surfacing. ``local.settings.json`` is a local signal,
    not deployable infrastructure, so it is excluded.
    """
    for infra in iter_project_files(path, ("*.bicep", "*.json")):
        if infra.name == "local.settings.json":
            continue
        try:
            text = infra.read_text(encoding="utf-8")
        except OSError:
            continue
        if _LINUX_FX_KEY_RE.search(text):
            return True
    return False


def _evaluate_flex_runtime_config(
    hosting_plan: Optional[str],
    runtime_name: Optional[str],
    runtime_version: Optional[str],
    *,
    linux_fx_present: bool,
) -> HandlerResult:
    """Validate a Flex Consumption app's ``functionAppConfig.runtime`` (issue #345).

    Only Flex apps are in scope (others SKIP). A ``linuxFxVersion`` declaration on
    a Flex app is a misconfiguration (WARN) because Flex ignores it. Otherwise the
    declared Python runtime version is validated against the Flex hosting-plan
    matrix (Flex supports through 3.14); an undeclared or non-Python runtime SKIPs.
    """
    if hosting_plan != FLEX_CONSUMPTION_PLAN:
        return _create_result(
            "skip",
            "Not a Flex Consumption app; functionAppConfig.runtime check skipped.",
        )

    if linux_fx_present:
        detail = (
            "linuxFxVersion is declared on a Flex Consumption app, which ignores "
            "it; declare the runtime under functionAppConfig.runtime (name/version) "
            "instead."
        )
        result = _create_result("fail", detail)
        result["severity"] = "warning"
        result["gate"] = False
        result["expected"] = "Runtime declared under functionAppConfig.runtime"
        result["actual"] = "linuxFxVersion declared on a Flex Consumption app"
        return result

    if runtime_name is None or runtime_version is None:
        return _create_result(
            "skip",
            "Flex Consumption app declares no functionAppConfig.runtime "
            "name/version; check skipped.",
        )

    if runtime_name != "python":
        return _create_result(
            "skip",
            f"Flex Consumption runtime is '{runtime_name}', not Python; "
            "Python runtime check skipped.",
        )

    if is_supported_python_for_plan(runtime_version, FLEX_CONSUMPTION_PLAN):
        return _create_result(
            "pass",
            f"Flex Consumption runtime Python {runtime_version} is supported.",
        )

    allowed = PYTHON_HOSTING_PLAN_MATRIX.get(FLEX_CONSUMPTION_PLAN, SUPPORTED_PYTHON_VERSIONS)
    supported_range = f"{allowed[0]}\u2013{allowed[-1]}" if allowed else "the supported set"
    detail = (
        f"Flex Consumption runtime Python {runtime_version} is not supported; "
        f"target a supported Python runtime ({supported_range})."
    )
    result = _create_result("fail", detail)
    result["severity"] = "error"
    result["gate"] = True
    result["expected"] = f"A supported Flex Consumption Python runtime ({supported_range})"
    result["actual"] = f"functionAppConfig.runtime = python {runtime_version}"
    return result


def _evaluate_flex_extension_version(ext_value: Optional[str]) -> HandlerResult:
    """Classify FUNCTIONS_EXTENSION_VERSION for a Flex Consumption app (issue #346).

    Flex Consumption does not support the ``FUNCTIONS_EXTENSION_VERSION`` app
    setting: it only runs on runtime v4 and the value is backend-managed. A
    missing value is therefore correct (SKIP), while an explicit value is a
    deprecated/unsupported setting worth surfacing (WARN).
    """
    if ext_value is None:
        return _create_result(
            "skip",
            "FUNCTIONS_EXTENSION_VERSION is not required on Flex Consumption "
            "(the runtime is v4 and backend-managed); check skipped.",
        )
    detail = (
        f"FUNCTIONS_EXTENSION_VERSION is set to '{ext_value}' but is not supported "
        "on Flex Consumption; the runtime is v4 and backend-managed. Remove the setting."
    )
    result = _create_result("fail", detail)
    result["severity"] = "warning"
    result["gate"] = False
    result["expected"] = "No FUNCTIONS_EXTENSION_VERSION on Flex Consumption"
    result["actual"] = f"FUNCTIONS_EXTENSION_VERSION = {ext_value}"
    return result


# Legacy app settings that Flex Consumption ignores, mapped to the replacement
# mechanism documented in Microsoft Learn's 'Flex Consumption plan deprecations'
# table (issue #350). LinuxFxVersion (owned by check_flex_runtime_config, #345)
# and FUNCTIONS_EXTENSION_VERSION (owned by check_functions_extension_version,
# #346) are deliberately excluded so this rule never double-reports them.
FLEX_DEPRECATED_APP_SETTINGS: dict[str, str] = {
    "FUNCTIONS_WORKER_RUNTIME": "replaced by 'name' under functionAppConfig.runtime.",
    "FUNCTIONS_WORKER_RUNTIME_VERSION": ("replaced by 'version' under functionAppConfig.runtime."),
    "FUNCTIONS_WORKER_PROCESS_COUNT": (
        "not valid on Flex Consumption; per-instance concurrency is platform-managed."
    ),
    "SCM_DO_BUILD_DURING_DEPLOYMENT": (
        "replaced by the remoteBuild parameter when deploying to Flex Consumption."
    ),
    "ENABLE_ORYX_BUILD": (
        "replaced by the remoteBuild parameter when deploying to Flex Consumption."
    ),
    "WEBSITE_CONTENTSHARE": "replaced by functionAppConfig's deployment section.",
    "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING": (
        "replaced by functionAppConfig's deployment section."
    ),
    "WEBSITE_RUN_FROM_PACKAGE": (
        "not used for deployments on Flex Consumption; use functionAppConfig.deployment."
    ),
    "WEBSITE_SKIP_CONTENTSHARE_VALIDATION": ("a content share isn't used on Flex Consumption."),
    "WEBSITE_VNET_ROUTE_ALL": (
        "not used for networking on Flex Consumption; configure VNet integration "
        "on the app's networking settings instead."
    ),
}


def _evaluate_flex_deprecated_settings(
    hosting_plan: Optional[str],
    app_settings: dict[str, str],
    *,
    catalog: Optional[Catalog] = None,
    setting_sources: Optional[dict[str, str]] = None,
) -> HandlerResult:
    """Warn on legacy app settings that Flex Consumption ignores (issue #350).

    Only Flex apps are in scope (others SKIP). Declared settings are matched
    against :data:`FLEX_DEPRECATED_APP_SETTINGS`; none present PASSes, otherwise a
    non-gating WARN lists each deprecated setting with its replacement mechanism
    and cites the catalog source. ``linuxFxVersion`` and
    ``FUNCTIONS_EXTENSION_VERSION`` are intentionally absent from the map (owned by
    #345 and #346), so this rule never emits a duplicate finding for them.
    """
    if hosting_plan != FLEX_CONSUMPTION_PLAN:
        return _create_result(
            "skip",
            "Not a Flex Consumption app; deprecated-app-settings check skipped.",
        )

    present = [name for name in FLEX_DEPRECATED_APP_SETTINGS if name in app_settings]
    if not present:
        return _create_result(
            "pass",
            "No deprecated Flex Consumption app settings are declared.",
        )

    lines = ["Deprecated app settings declared on a Flex Consumption app:"]
    lines.extend(f"  - {name}: {FLEX_DEPRECATED_APP_SETTINGS[name]}" for name in present)
    lines.append(
        "Flex Consumption ignores these settings; remove them and use the listed "
        "replacement mechanism."
    )
    detail = "\n".join(lines)
    # Cite the declaring file per deprecated setting (#394/#408): local.settings
    # entries map to local.settings.json; infra entries carry ingest provenance.
    sources = setting_sources or {}
    locations: list[dict[str, object]] = [
        {
            "file": sources.get(name),
            "message": f"Deprecated Flex Consumption app setting: {name}",
        }
        for name in present[:10]
    ]
    result = _create_result(
        "fail",
        detail,
        file=sources.get(present[0]) if present else None,
        locations=locations,
    )
    result["severity"] = "warning"
    result["gate"] = False
    expected = "No deprecated legacy app settings on Flex Consumption"
    actual = "Deprecated app settings declared: " + ", ".join(present)
    cat = load_catalog() if catalog is None else catalog
    fact = cat.flex_deprecated_settings_fact()
    if fact is not None:
        _attach_catalog_evidence(result, fact, cat, detail=detail, expected=expected, actual=actual)
    else:
        result["expected"] = expected
        result["actual"] = actual
    return result


def _evaluate_flex_deployment_storage(
    hosting_plan: Optional[str],
    storage: Optional[dict[str, object]],
) -> HandlerResult:
    """Validate a Flex Consumption app's deployment storage shape (issue #351).

    Only Flex apps are in scope (others SKIP). Flex stores the deployment package
    in a blob container declared under ``functionAppConfig.deployment.storage``.
    When no such block is declared in infra the check SKIPs gracefully; otherwise
    obviously wrong shapes are flagged (non-gating WARN): a missing container URL
    (``value``), or missing/incomplete ``authentication`` (a managed identity or a
    named storage connection string). A well-formed block PASSes. This is a static
    shape check only; the storage account is never contacted.
    """
    if hosting_plan != FLEX_CONSUMPTION_PLAN:
        return _create_result(
            "skip",
            "Not a Flex Consumption app; deployment-storage check skipped.",
        )
    if storage is None:
        return _create_result(
            "skip",
            "Flex Consumption app declares no functionAppConfig.deployment.storage "
            "in infra; deployment-storage check skipped.",
        )

    problems: list[str] = []
    value = storage.get("value")
    if not isinstance(value, str) or not value.strip():
        problems.append(
            "no deployment container is specified (functionAppConfig.deployment.storage.value)"
        )

    authentication = storage.get("authentication")
    if not isinstance(authentication, dict):
        problems.append(
            "no authentication is configured; use a managed identity or a storage "
            "account connection string"
        )
    else:
        auth_type = authentication.get("type")
        if not isinstance(auth_type, str) or not auth_type.strip():
            problems.append("deployment storage authentication is missing a 'type'")
        elif auth_type == "StorageAccountConnectionString":
            name = authentication.get("storageAccountConnectionStringName")
            if not isinstance(name, str) or not name.strip():
                problems.append(
                    "connection-string authentication is missing "
                    "'storageAccountConnectionStringName'"
                )

    if not problems:
        return _create_result(
            "pass",
            "Flex Consumption deployment storage is configured (container + authentication).",
        )

    lines = ["Flex Consumption deployment storage is misconfigured:"]
    lines.extend(f"  - {problem}" for problem in problems)
    lines.append(
        "Declare a blob container under functionAppConfig.deployment.storage with "
        "a value URL and authentication (managed identity or connection string)."
    )
    detail = "\n".join(lines)
    result = _create_result("fail", detail)
    result["severity"] = "warning"
    result["gate"] = False
    result["expected"] = (
        "functionAppConfig.deployment.storage with a container URL and authentication"
    )
    result["actual"] = "; ".join(problems)
    return result


# Local-only signals that are never deployable infrastructure: the live
# local.settings.json and its *.sample.json template (#393).
DEPLOY_CONFIG_SKIP_NAMES = frozenset({"local.settings.json", "local.settings.sample.json"})


class DeploymentHandlers:
    """Deployment-correctness handlers and evaluators.

    Flex Consumption config, FUNCTIONS_EXTENSION_VERSION, linuxFxVersion,
    host.json/site config, dev-storage leak.
    """

    @_rule_handler
    def _handle_flex_runtime_config(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Validate a Flex Consumption app's ``functionAppConfig.runtime`` (issue #345).

        Flex Consumption declares its runtime under ``functionAppConfig.runtime``
        (name/version) rather than ``linuxFxVersion``. This check is scoped to Flex
        apps: it WARNs when a legacy ``linuxFxVersion`` is present (Flex ignores it)
        and otherwise validates the declared Python runtime against the Flex
        hosting-plan matrix.
        """
        target_config = context.get("target_config") if context is not None else None
        hosting_plan: Optional[str] = None
        runtime_name: Optional[str] = None
        runtime_version: Optional[str] = None
        if target_config is not None:
            hosting_plan = target_config.hosting_plan.value
            runtime_name = target_config.runtime_name.value
            runtime_version = target_config.runtime_version.value
        linux_fx_present = (
            hosting_plan == FLEX_CONSUMPTION_PLAN and _infra_declares_linux_fx_version(path)
        )
        result = _evaluate_flex_runtime_config(
            hosting_plan,
            runtime_name,
            runtime_version,
            linux_fx_present=linux_fx_present,
        )
        if result["status"] not in ("pass", "skip") and target_config is not None:
            source = target_config.runtime_name.source
            if source and not source.startswith("unknown"):
                result["file"] = source
                result.setdefault("locations", [{"file": source}])
        return result

    @_rule_handler
    def _handle_flex_deprecated_settings(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Warn when a Flex Consumption app declares deprecated legacy app settings (#350).

        Flex Consumption ignores a set of legacy app settings (worker-runtime
        selection, Oryx/remote-build toggles, Azure Files content-share settings,
        run-from-package, and VNet route-all). This check is scoped to Flex apps and
        WARNs (non-gating) with a per-setting replacement mechanism. ``linuxFxVersion``
        and ``FUNCTIONS_EXTENSION_VERSION`` are owned by check_flex_runtime_config
        (#345) and check_functions_extension_version (#346), so they are never
        reported here.
        """
        target_config = context.get("target_config") if context is not None else None
        if target_config is None:
            return _create_result(
                "skip",
                "Deployment target could not be resolved; "
                "Flex deprecated-app-settings check skipped.",
            )
        setting_sources = {**target_config.app_settings_files}
        for local_name in local_settings_values(path):
            setting_sources.setdefault(local_name, "local.settings.json")
        return _evaluate_flex_deprecated_settings(
            target_config.hosting_plan.value,
            target_config.app_settings,
            setting_sources=setting_sources,
        )

    @_rule_handler
    def _handle_flex_deployment_storage(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Validate a Flex Consumption app's deployment storage shape (#351).

        Flex Consumption stores the deployment package in a blob container declared
        under ``functionAppConfig.deployment.storage``. This check is scoped to Flex
        apps (others SKIP). When infra declares no such block it SKIPs gracefully;
        otherwise obviously wrong shapes WARN (non-gating): a missing container URL
        or missing/incomplete authentication. The storage account is never
        contacted -- this is a static shape check only.
        """
        target_config = context.get("target_config") if context is not None else None
        if target_config is None:
            return _create_result(
                "skip",
                "Deployment target could not be resolved; Flex deployment-storage check skipped.",
            )
        hosting_plan = target_config.hosting_plan.value
        storage = (
            flex_deployment_storage_shape(path) if hosting_plan == FLEX_CONSUMPTION_PLAN else None
        )
        result = _evaluate_flex_deployment_storage(hosting_plan, storage)
        if result["status"] not in ("pass", "skip") and target_config is not None:
            source = target_config.deployment_storage.source
            if source and not source.startswith("unknown"):
                result["file"] = source
        return result

    @_rule_handler
    def _handle_functions_extension_version(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Flag a missing, legacy, or non-v4 FUNCTIONS_EXTENSION_VERSION setting.

        The v1/v2/v3 runtimes are retired, so ``local.settings.json`` should pin
        the extension version to the current runtime (``~4`` by default). The
        expected value is overridable via ``condition.value``.

        Flex Consumption is special-cased (issue #346): it does not support this
        app setting at all, so a missing value SKIPs and an explicit value WARNs
        instead of following the legacy-runtime logic.
        """
        target_config = context.get("target_config") if context is not None else None
        if target_config is not None and target_config.hosting_plan.value == FLEX_CONSUMPTION_PLAN:
            return _evaluate_flex_extension_version(target_config.extension_version.value)
        condition = rule.get("condition", {}) or {}
        expected = str(condition.get("value") or "~4")
        settings_path = path / "local.settings.json"
        if not settings_path.exists():
            return _create_result(
                "skip",
                "local.settings.json not present; FUNCTIONS_EXTENSION_VERSION check skipped",
            )
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return _handle_specific_exceptions("reading local.settings.json", exc)
        values = data.get("Values") if isinstance(data, dict) else None
        current = values.get("FUNCTIONS_EXTENSION_VERSION") if isinstance(values, dict) else None
        if current is None:
            return _create_result(
                "fail",
                "FUNCTIONS_EXTENSION_VERSION is not set in local.settings.json; "
                f"pin it to '{expected}' for the current Azure Functions runtime.",
                file="local.settings.json",
            )
        if str(current).strip() != expected:
            return _create_result(
                "fail",
                f"FUNCTIONS_EXTENSION_VERSION is '{current}', expected '{expected}'. "
                "Legacy runtimes (~1/~2/~3) are retired; target the v4 runtime.",
                file="local.settings.json",
            )
        return _create_result("pass", f"FUNCTIONS_EXTENSION_VERSION is '{expected}'")

    @_rule_handler
    def _handle_linux_fx_version(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Validate any Python ``linuxFxVersion`` declared in infra (bicep) config.

        Scoped to legacy Linux / Premium / Dedicated / classic Consumption apps.
        Flex Consumption declares its runtime under ``functionAppConfig.runtime``
        and ignores ``linuxFxVersion``, so Flex apps SKIP here and are handled by
        ``check_flex_runtime_config`` (issue #345). When such a declaration targets
        a Python version outside the supported set it is flagged; when no Python
        ``linuxFxVersion`` is determinable the check is skipped.
        """
        target_config = context.get("target_config") if context is not None else None
        if target_config is not None and target_config.hosting_plan.value == FLEX_CONSUMPTION_PLAN:
            return _create_result(
                "skip",
                "Flex Consumption app; linuxFxVersion is not used (see check_flex_runtime_config).",
            )
        findings: list[tuple[str, str]] = []
        pattern = re.compile(r"linuxFxVersion['\"]?\s*[:=]\s*['\"]?[Pp]ython\|(\d+\.\d+)")
        for bicep in iter_project_files(path, "*.bicep"):
            try:
                text = bicep.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in pattern.finditer(text):
                findings.append((str(bicep.relative_to(path)), match.group(1)))
        if not findings:
            return _create_result(
                "skip", "No Python linuxFxVersion found in infra config; check skipped"
            )
        unsupported = [(loc, ver) for loc, ver in findings if not is_supported_python_target(ver)]
        if not unsupported:
            return _create_result(
                "pass", "linuxFxVersion Python runtime(s) target a supported version"
            )
        supported_range = f"{SUPPORTED_PYTHON_VERSIONS[0]}\u2013{SUPPORTED_PYTHON_VERSIONS[-1]}"
        detail = "\n".join(
            [
                "Unsupported Python linuxFxVersion runtime(s) in infra config:",
                *[f"- {loc}: Python|{ver}" for loc, ver in unsupported[:10]],
                "",
                f"Fix: target a supported Python runtime ({supported_range}).",
            ]
        )
        return _create_result(
            "fail",
            detail,
            file=findings[0][0] if findings else None,
            locations=[
                {"file": loc, "message": f"linuxFxVersion Python|{ver} is unsupported"}
                for loc, ver in findings[:10]
            ],
        )

    @_rule_handler
    def _handle_dev_storage_connection(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Flag the Azurite/dev-storage emulator connection in deployable config.

        ``AzureWebJobsStorage=UseDevelopmentStorage=true`` targets the local
        Azurite emulator and must never reach a deployed app. It is expected in
        ``local.settings.json`` (which is not deployed) but is a deploy-risk when
        present in infra templates (bicep/ARM) that provision app settings.
        """
        emulator = "UseDevelopmentStorage=true"
        findings: list[str] = []
        candidates = list(iter_project_files(path, "*.bicep")) + [
            p for p in iter_project_files(path, "*.json") if p.name not in DEPLOY_CONFIG_SKIP_NAMES
        ]
        for candidate in sorted(candidates):
            try:
                text = candidate.read_text(encoding="utf-8")
            except OSError:
                continue
            if "AzureWebJobsStorage" in text and emulator in text:
                findings.append(str(candidate.relative_to(path)))
        if not findings:
            return _create_result(
                "pass", "No dev-storage emulator connection found in deployable config"
            )
        detail = "\n".join(
            [
                "Dev-storage emulator connection in deployable config (ships to production):",
                *[f"- {loc}" for loc in findings[:10]],
                "",
                "Fix: provision a real storage account connection for AzureWebJobsStorage "
                "in deployment templates; keep UseDevelopmentStorage=true only in "
                "local.settings.json.",
            ]
        )
        return _create_result(
            "fail",
            detail,
            file=findings[0] if findings else None,
            locations=[
                {"file": loc, "message": "Dev-storage emulator connection ships to production"}
                for loc in findings[:10]
            ],
        )

    @_rule_handler
    def _handle_host_json_property(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check a property exists in host.json using simple jsonpath-like pointer."""
        condition = rule.get("condition", {}) or {}
        jsonpath = condition.get("jsonpath")
        if not jsonpath or not isinstance(jsonpath, str):
            return _create_result(
                "fail",
                "Missing or invalid 'jsonpath' in condition",
                file="host.json",
            )
        host_path = path / "host.json"
        if not host_path.exists():
            return _create_result("fail", "host.json not found")
        try:
            host_data = json.loads(host_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return _handle_specific_exceptions("reading host.json", exc)
        if _resolve_host_json_path(host_data, jsonpath) is _HOST_JSON_MISSING:
            return _create_result("fail", f"host.json property '{jsonpath}' not found")
        return _create_result("pass", f"host.json contains '{jsonpath}'")

    @_rule_handler
    def _handle_host_json_version(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check that host.json declares \"version\": \"2.0\"."""
        host_path = path / "host.json"
        if not host_path.exists():
            return _create_result(
                "fail",
                "host.json not found",
                file="host.json",
            )
        try:
            host_data = json.loads(host_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            msg = f"host.json is not valid JSON: {exc}"
            return _create_result("fail", msg, internal_error=True)
        except Exception as exc:
            return _handle_specific_exceptions("reading host.json", exc)
        version = host_data.get("version") if isinstance(host_data, dict) else None
        if version == "2.0":
            return _create_result("pass", 'host.json version is "2.0"')
        return _create_result(
            "fail",
            f'host.json version is {version!r}, expected "2.0"',
        )

    @_rule_handler
    def _handle_local_settings_security(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check that local.settings.json is not tracked by git (security risk)."""
        import subprocess  # nosec B404

        settings_path = path / "local.settings.json"
        if not settings_path.exists():
            return _create_result("skip", "local.settings.json not present; check skipped")

        # Check if the file is tracked by git
        try:
            result = subprocess.run(  # nosec B603 B607
                ["git", "-C", str(path), "ls-files", "--error-unmatch", str(settings_path)],
                capture_output=True,
                timeout=10,
            )
            tracked = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            # git not available or not a git repo — skip check
            return _create_result(
                "skip",
                "git not available; local.settings.json git-tracking check skipped",
            )

        if tracked:
            return _create_result(
                "fail",
                "local.settings.json is tracked by git and may expose secrets"
                " — add it to .gitignore",
                file="local.settings.json",
            )
        return _create_result("pass", "local.settings.json is not tracked by git")

    @_rule_handler
    def _handle_host_json_extension_bundle_version(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check that extensionBundle in host.json uses the recommended v4 range."""
        host_path = path / "host.json"
        if not host_path.exists():
            return _create_result(
                "fail",
                "host.json not found",
                file="host.json",
            )
        try:
            host_data = json.loads(host_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return _handle_specific_exceptions("reading host.json", exc)

        if not isinstance(host_data, dict):
            return _create_result("fail", "host.json is not a JSON object")

        bundle = host_data.get("extensionBundle")
        if bundle is None:
            return _create_result("fail", "extensionBundle not configured in host.json")

        if not isinstance(bundle, dict):
            return _create_result("fail", "extensionBundle in host.json is not an object")

        bundle_id = bundle.get("id", "")
        bundle_version = bundle.get("version", "")

        # Recommended bundle: id=Microsoft.Azure.Functions.ExtensionBundle, version=[4.*, 5.0.0)
        recommended_id = "Microsoft.Azure.Functions.ExtensionBundle"
        if bundle_id != recommended_id:
            return _create_result(
                "fail",
                f"extensionBundle id '{bundle_id}' is not the recommended '{recommended_id}'",
            )

        version_str = str(bundle_version).strip()
        # Parse a NuGet-style range: [lower, upper) with */numeric version parts.
        range_match = re.match(
            r"^([\[(])\s*"
            r"(\d+)(?:\.(\d+|\*))?(?:\.(\d+|\*))?\s*,\s*"
            r"(\d+)(?:\.(\d+|\*))?(?:\.(\d+|\*))?\s*"
            r"([\])])$",
            version_str,
        )
        if range_match is None:
            return _create_result(
                "fail",
                f"extensionBundle version '{version_str}' is not a valid range;"
                " use the recommended [4.0.0, 5.0.0)",
            )

        lower_bracket = range_match.group(1)
        lower_major = int(range_match.group(2))
        upper_major = int(range_match.group(5))
        upper_minor_raw = range_match.group(6)
        upper_patch_raw = range_match.group(7)
        upper_bracket = range_match.group(8)

        if lower_major < 4:
            return _create_result(
                "fail",
                f"extensionBundle version '{version_str}' is below"
                " recommended v4 range — upgrade to [4.0.0, 5.0.0)",
            )

        # Valid v4: lower bound inclusive starting at major 4, upper bound
        # exclusive at exactly major 5 (i.e. [4.x, 5.0.0)).
        # The exclusive upper bound must be exactly 5.0.0. An absent minor/patch
        # component defaults to 0; a wildcard ('*') or non-zero component (e.g.
        # 5.1.0) widens the range beyond the recommended bound and must fail.
        upper_minor_zero = upper_minor_raw in (None, "0")
        upper_patch_zero = upper_patch_raw in (None, "0")
        is_valid_v4 = (
            lower_bracket == "["
            and lower_major == 4
            and upper_major == 5
            and upper_minor_zero
            and upper_patch_zero
            and upper_bracket == ")"
        )
        if is_valid_v4:
            return _create_result(
                "pass",
                f"extensionBundle uses recommended v4 range: {version_str}",
            )

        return _create_result(
            "fail",
            f"extensionBundle version '{version_str}' does not match the"
            " recommended v4 range [4.0.0, 5.0.0); the upper bound must be an"
            " exclusive 5.0.0",
        )
