import ast
from collections import defaultdict
import importlib.resources
import json
from pathlib import Path
import time
from typing import Literal, Mapping, Optional, TypedDict, cast

from jsonschema import ValidationError, validate

from azure_functions_doctor.handlers import (
    HandlerResult,
    Rule,
    RuleContext,
    _discover_functionapp_aliases,
    _iter_project_py_contents,
    _source_contains_ast,
    generic_handler,
    iter_project_files,
    load_doctor_config,
    reset_extra_excludes,
    resolve_target_config,
    set_extra_excludes,
)
from azure_functions_doctor.logging_config import get_logger, log_rule_execution

logger = get_logger(__name__)

ProgrammingModel = Literal["v2", "unsupported_v1", "mixed", "unknown"]

_VALID_SEVERITIES = ("error", "warning", "info")
_VALID_TIERS = ("core", "extended", "experimental")

# Finding Contract v2 (issue #348): the machine-output schema version for the
# ``json`` format. Bumped from the implicit v1 (which carried only rule_id /
# status / severity / tier) to v2, which adds auditable evidence and freshness
# fields plus an ``analysis`` block. This is independent of the SARIF schema
# version ("2.1.0").
FINDING_SCHEMA_VERSION = "2.0"

# Finding Contract v2 evidence / freshness fields carried from a handler result
# into the emitted finding. All are optional strings.
FINDING_EVIDENCE_KEYS = (
    "evidence",
    "expected",
    "actual",
    "source_url",
    "last_verified",
    "catalog_version",
)


def _resolve_severity(rule: Rule) -> str:
    """Resolve a rule's runtime severity, falling back to ``required``."""
    severity = rule.get("severity")
    if severity in _VALID_SEVERITIES:
        return str(severity)
    return "error" if rule.get("required", True) else "warning"


def _resolve_gate(rule: Rule) -> bool:
    """Whether a failing rule gates the run, independent of severity."""
    gate = rule.get("gate")
    if isinstance(gate, bool):
        return gate
    return bool(rule.get("required", True))


def _resolve_tier(rule: Rule) -> str:
    """Resolve a rule's maturity tier, falling back to ``required``."""
    tier = rule.get("tier")
    if tier in _VALID_TIERS:
        return str(tier)
    return "core" if rule.get("required", True) else "extended"


# Rule-profile membership lives in a dependency-free module so lightweight
# tooling can share the same source of truth; re-exported here for runtime use.
from azure_functions_doctor.profiles import (  # noqa: E402
    DEV_ENVIRONMENT_RULES,
    PROFILE_NAMES,
    profiles_for_rule,
    rule_matches_profile,
)

__all__ = [
    "DEV_ENVIRONMENT_RULES",
    "PROFILE_NAMES",
    "profiles_for_rule",
    "rule_matches_profile",
]


class CheckResult(TypedDict, total=False):
    rule_id: str
    label: str
    value: str
    status: str
    severity: str
    tier: str
    hint: str
    hint_url: str
    file: str
    line: int
    end_line: int
    column: int
    # Per-finding locations (issues #394/#395); SARIF emits one result per entry.
    locations: list[dict[str, object]]
    # Finding Contract v2 (issue #348): auditable evidence + freshness metadata.
    evidence: str
    expected: str
    actual: str
    source_url: str
    last_verified: str
    catalog_version: str
    analysis: dict[str, str]


class SectionResult(TypedDict):
    title: str
    category: str
    status: str  # 'pass' or 'fail'
    items: list[CheckResult]


def _apply_finding_contract_v2(item: CheckResult, result: HandlerResult) -> None:
    """Attach Finding Contract v2 metadata (issue #348) to a finding.

    Copies any auditable evidence / freshness fields a handler emitted
    (``evidence``, ``expected``, ``actual``, ``source_url``, ``last_verified``,
    ``catalog_version``) into the finding, and always records the deterministic
    analysis marker. ``analysis.type = "deterministic"`` is preferred over a
    ``confidence`` float so this diagnostic output stays cleanly separated from
    any future agent-inferred findings.
    """
    result_map = cast(Mapping[str, object], result)
    item_map = cast("dict[str, object]", item)
    for key in FINDING_EVIDENCE_KEYS:
        value = result_map.get(key)
        if isinstance(value, str) and value:
            item_map[key] = value
    item["analysis"] = {"type": "deterministic"}


class Doctor:
    """
    Diagnostic runner for Azure Functions apps.

    Loads checks from the built-in Azure Functions Python v2 rule asset
    located at `azure_functions_doctor.assets.rules.v2.json`.
    """

    def __init__(
        self,
        path: str = ".",
        profile: Optional[str] = None,
        rules_path: Optional[Path] = None,
        target_python: Optional[str] = None,
        deployment_mode: str = "remote-build",
        hosting_plan: Optional[str] = None,
    ) -> None:
        self.project_path: Path = Path(path).resolve()
        self.profile = profile
        self.target_python: Optional[str] = target_python
        self.deployment_mode: str = deployment_mode
        self.hosting_plan: Optional[str] = hosting_plan
        self.rules_path: Optional[Path] = None
        if rules_path is not None:
            resolved = rules_path.resolve()
            if not resolved.is_file():
                raise ValueError(f"rules_path must be an existing file: {resolved}")
            self.rules_path = resolved
        # Config-based suppression / exclusion (issue #290). CLI selections
        # (profile, rules_path) take precedence for ruleset selection; the
        # config ``ignore``/``exclude`` layer on top of the resolved run.
        doctor_config = load_doctor_config(self.project_path)
        self.ignore_rules: set[str] = set(doctor_config["ignore"])
        self.exclude_globs: list[str] = list(doctor_config["exclude"])
        self.programming_model: ProgrammingModel = self._detect_programming_model()

    def get_report_properties(self) -> dict[str, Optional[str]]:
        """Return top-level report properties shared across output formats."""
        return {
            "programming_model": self.programming_model,
            "target_python": self.target_python,
            "deployment_mode": self.deployment_mode,
            "hosting_plan": self.hosting_plan,
        }

    def _detect_programming_model(self) -> ProgrammingModel:
        """Detect the Azure Functions programming model state for the project."""
        has_v1_signals = self._has_v1_signals()
        has_v2_signals = self._has_v2_signals()

        if has_v1_signals and has_v2_signals:
            programming_model: ProgrammingModel = "mixed"
        elif has_v1_signals:
            programming_model = "unsupported_v1"
        elif has_v2_signals:
            programming_model = "v2"
        else:
            programming_model = "unknown"

        logger.debug(
            "Programming model detected: %s (v1=%s, v2=%s)",
            programming_model,
            has_v1_signals,
            has_v2_signals,
        )
        return programming_model

    def _has_v1_signals(self) -> bool:
        """Check if the project contains legacy v1 function.json files."""
        for function_json in iter_project_files(self.project_path, "function.json"):
            logger.debug("Detected v1 signal: %s", function_json)
            return True
        return False

    def _has_v2_signals(self) -> bool:
        """Check if the project contains v2 app objects or decorators."""
        for py_file, content in _iter_project_py_contents(self.project_path):
            if self._source_contains_v2_app_object(content):
                logger.debug("Detected v2 FunctionApp/Blueprint signal: %s", py_file)
                return True
        return self._has_v2_decorators()

    def _source_contains_v2_app_object(self, source: str) -> bool:
        """Check for AST-level FunctionApp()/Blueprint() usage."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False

        discovered_aliases = _discover_functionapp_aliases(source)
        if discovered_aliases != {"app"}:
            return True

        target_names = {"FunctionApp", "Blueprint"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_node = node.func
            if isinstance(func_node, ast.Attribute) and func_node.attr in target_names:
                return True
            if isinstance(func_node, ast.Name) and func_node.id in target_names:
                return True
        return False

    def _has_v2_decorators(self) -> bool:
        """Check if the project uses v2 decorators using AST-based detection.

        Uses the shared ``_source_contains_ast`` helper (which auto-discovers
        ``FunctionApp`` / ``Blueprint`` aliases) and the project file iterator
        that respects excluded directories.
        """
        for _py_file, content in _iter_project_py_contents(self.project_path):
            if _source_contains_ast(content, "app"):
                return True
        return False

    def _build_programming_model_failure(self) -> SectionResult:
        """Build the fail-fast section for unsupported or undetected models."""
        messages: dict[ProgrammingModel, tuple[str, str, str]] = {
            "unsupported_v1": (
                "Unsupported programming model: Python v1",
                (
                    "Detected legacy function.json files. azure-functions-doctor supports "
                    "the Python v2 decorator model only."
                ),
                (
                    "Migrate to the Python v2 programming model "
                    "(function_app.py + func.FunctionApp() with decorators), or skip "
                    "azure-functions-doctor for this repository."
                ),
            ),
            "mixed": (
                "Mixed programming model detected",
                "Both v1 (function.json) and v2 (FunctionApp/decorators) signals were found.",
                (
                    "Remove legacy function.json based functions, or migrate fully to the "
                    "v2 programming model."
                ),
            ),
            "unknown": (
                "Python v2 programming model was not detected",
                "No function_app.py, FunctionApp()/Blueprint() usage, or trigger decorators found.",
                (
                    "Expected: function_app.py with func.FunctionApp() and trigger "
                    "decorators (@app.route, @app.timer_trigger, etc.). This tool "
                    "supports v2 projects only."
                ),
            ),
            "v2": ("", "", ""),
        }
        label, value, hint = messages[self.programming_model]
        return {
            "title": "Programming Model",
            "category": "programming_model",
            "status": "fail",
            "items": [
                {
                    "rule_id": "check_programming_model_v2",
                    "label": label,
                    "value": value,
                    "status": "fail",
                    "severity": "error",
                    "tier": "core",
                    "hint": hint,
                    "analysis": {"type": "deterministic"},
                }
            ],
        }

    def load_rules(self) -> list[Rule]:
        """Load and validate rules from a custom path or the built-in v2 ruleset."""
        if self.rules_path is not None:
            with self.rules_path.open(encoding="utf-8") as f:
                rules: list[Rule] = json.load(f)
        else:
            rules = self._load_v2_rules()

        self._validate_rules(rules)
        return sorted(rules, key=lambda r: r.get("check_order", 999))

    def _validate_rules(self, rules: list[Rule]) -> None:
        schema_path = importlib.resources.files("azure_functions_doctor.schemas").joinpath(
            "rules.schema.json"
        )
        with schema_path.open(encoding="utf-8") as f:
            schema = json.load(f)

        try:
            validate(instance=rules, schema=schema)
        except ValidationError as exc:
            raise ValueError(f"Invalid rules file: {str(exc)}") from exc

    def _load_v2_rules(self) -> list[Rule]:
        """Load complete v2 rules set."""
        files_obj = importlib.resources.files("azure_functions_doctor.assets")

        # Load v2 rules from assets/rules/v2.json only
        try:
            rules_path = files_obj.joinpath("rules/v2.json")
            with rules_path.open(encoding="utf-8") as f:
                v2_rules = json.load(f)
        except FileNotFoundError as e:
            logger.error("v2.json not found")
            raise RuntimeError("v2.json not found") from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in v2.json: {e}")
            raise RuntimeError(f"Failed to parse v2.json: {e}") from e

        return sorted(list(v2_rules), key=lambda r: r.get("check_order", 999))

    def run_all_checks(self, rules: Optional[list[Rule]] = None) -> list[SectionResult]:
        rules = self.load_rules() if rules is None else rules
        if self.profile is not None and self.profile != "full":
            if self.profile not in PROFILE_NAMES:
                raise ValueError("Profile must be one of: " + ", ".join(PROFILE_NAMES))
            rules = [rule for rule in rules if rule_matches_profile(rule, self.profile)]

        if self.programming_model != "v2":
            logger.info(
                "Skipping rule execution for non-v2 project: programming_model=%s",
                self.programming_model,
            )
            return [self._build_programming_model_failure()]

        grouped: dict[str, list[Rule]] = defaultdict(list)

        for rule in rules:
            grouped[rule.get("section", "unknown")].append(rule)

        results: list[SectionResult] = []
        # Layer config ``exclude`` globs on top of EXCLUDED_PROJECT_DIRS for the
        # duration of this run (issue #290). Each run sets its own value first,
        # so state never leaks between runs.
        exclude_token = set_extra_excludes(self.project_path, self.exclude_globs)
        context: RuleContext = {
            "target_python": self.target_python,
            "deployment_mode": self.deployment_mode,
            "target_config": resolve_target_config(
                self.project_path,
                {
                    "hosting_plan": self.hosting_plan,
                    "runtime_version": self.target_python,
                    "deployment_mode": self.deployment_mode,
                },
            ),
        }

        for section, checks in grouped.items():
            section_result: SectionResult = {
                "title": section.replace("_", " ").title(),
                "category": section,
                "status": "pass",
                "items": [],
            }

            for rule in checks:
                rule_id = rule.get("id", "unknown_rule")
                # Config-based suppression (issue #290): report ignored rules
                # with the explicit ``skip`` status instead of executing them.
                if rule_id in self.ignore_rules:
                    skip_item: CheckResult = {
                        "rule_id": rule_id,
                        "label": rule.get("label", rule_id),
                        "value": ("Suppressed by pyproject [tool.azure-functions-doctor].ignore"),
                        "status": "skip",
                        "severity": _resolve_severity(rule),
                        "tier": _resolve_tier(rule),
                    }
                    section_result["items"].append(skip_item)
                    continue
                # Time rule execution for logging
                rule_start = time.time()
                result = generic_handler(rule, self.project_path, context)
                rule_duration_ms = (time.time() - rule_start) * 1000

                handler_status = result.get("status", "fail")
                log_rule_execution(
                    rule.get("id", "unknown_rule"),
                    rule.get("type", "unknown_type"),
                    handler_status,
                    rule_duration_ms,
                )

                # Canonical mapping driven by explicit severity/gate/tier
                # (each derived from ``required`` when not set on the rule):
                #   pass -> pass, skip -> skip; a failing handler maps to
                #   "fail" when severity is "error", otherwise "warn". The
                #   section is only gated to fail when the rule is a gate.
                severity = _resolve_severity(rule)
                gate = _resolve_gate(rule)
                tier = _resolve_tier(rule)
                # A handler may refine severity/gate per finding (issue #343):
                # e.g. a runtime-lifecycle check WARNs on a retiring runtime but
                # FAILs on one past end-of-support. When absent, rule defaults win.
                handler_severity = result.get("severity")
                if handler_severity in _VALID_SEVERITIES:
                    severity = str(handler_severity)
                handler_gate = result.get("gate")
                if isinstance(handler_gate, bool):
                    gate = handler_gate
                rule_id = rule.get("id", "unknown_rule")
                if handler_status == "pass":
                    canonical = "pass"
                elif handler_status == "skip":
                    canonical = "skip"
                else:
                    canonical = "fail" if severity == "error" else "warn"

                failed = handler_status not in ("pass", "skip")
                detail = result.get("detail", "")
                # A failing rule is "optional" when it does not gate the run,
                # independent of its display severity (a gate rule may still
                # carry severity "warning"/"info").
                if failed and not gate:
                    detail += " (optional)"

                item: CheckResult = {
                    "rule_id": rule_id,
                    "label": rule.get("label", rule_id),
                    "value": detail,
                    "status": canonical,
                    "severity": severity,
                    "tier": tier,
                }

                _apply_finding_contract_v2(item, result)

                if failed and gate:
                    section_result["status"] = "fail"

                if "hint" in rule:
                    item["hint"] = rule["hint"]

                if "hint_url" in rule and rule["hint_url"]:
                    item["hint_url"] = rule["hint_url"]

                if "file" in result:
                    item["file"] = result["file"]
                if "line" in result:
                    item["line"] = result["line"]
                if "end_line" in result:
                    item["end_line"] = result["end_line"]
                if "column" in result:
                    item["column"] = result["column"]
                if "locations" in result:
                    item["locations"] = result["locations"]

                section_result["items"].append(item)

            results.append(section_result)

        reset_extra_excludes(exclude_token)
        return results
