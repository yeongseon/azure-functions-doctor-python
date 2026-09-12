"""Dependency-manifest handlers (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

import importlib.util
from pathlib import Path
from typing import Optional

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from azure_functions_doctor.handlers._helpers import (
    HandlerResult,
    Rule,
    RuleContext,
    _create_result,
    _detect_native_dependency_risks,
    _handle_specific_exceptions,
    _parse_requirements_names,
    _rule_handler,
    is_local_prebuilt_deployment,
    parse_package,
    parse_target,
    pyproject_declares_dependencies,
    pyproject_dependency_names,
)


class DependencyHandlers:
    """Dependency-manifest handlers.

    requirements.txt / pyproject declarations, native-deployment risk, pinning.
    """

    @_rule_handler
    def _handle_dependency_manifest(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Validate the dependency manifest against the deployment mode.

        Azure Functions performs a *remote build* by default, installing
        dependencies from ``requirements.txt`` on the server. A pyproject-only
        project therefore passes only for a local/prebuilt deployment; under
        remote build a missing ``requirements.txt`` is flagged because the
        server never reads ``pyproject.toml``.
        """
        condition = rule.get("condition", {}) or {}
        target = parse_target(condition) or "requirements.txt"
        req_path = path / target
        if req_path.is_file():
            return _create_result("pass", f"{req_path} exists")
        if pyproject_declares_dependencies(path):
            if is_local_prebuilt_deployment(path, context):
                return _create_result(
                    "pass",
                    f"{req_path} not found; dependencies declared in pyproject.toml "
                    "(local/prebuilt deployment)",
                )
            detail = (
                f"{req_path} not found; dependencies are only declared in "
                "pyproject.toml. Azure remote build installs from requirements.txt, "
                "so generate one (e.g. 'pip freeze > requirements.txt') or deploy "
                "with a local/prebuilt build (--deployment-mode local)."
            )
            if not rule.get("required", True):
                detail += " (optional)"
            return _create_result(
                "fail",
                detail,
                file="requirements.txt",
            )
        detail = f"{req_path} not found and pyproject.toml declares no dependencies"
        if not rule.get("required", True):
            detail += " (optional)"
        return _create_result("fail", detail)

    @_rule_handler
    def _handle_package_installed(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Handle Python package installation checks."""
        condition = rule.get("condition", {}) or {}
        target = parse_target(condition)

        if not target:
            return _create_result(
                "fail",
                "Missing package name",
                file="requirements.txt",
            )

        import_path_str: str = str(target)
        spec = importlib.util.find_spec(import_path_str)
        if spec is not None:
            return _create_result("pass", f"Module '{import_path_str}' is installed")
        return _create_result("fail", f"Module '{import_path_str}' is not installed")

    @_rule_handler
    def _handle_package_declared(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check that a package name appears in requirements.txt (declaration-level)."""
        condition = rule.get("condition", {}) or {}
        params = parse_package(condition)
        if params is None:
            return _create_result(
                "fail",
                "Missing 'package' in condition",
                file="requirements.txt",
            )
        package_name, req_file = params
        normalized_target = canonicalize_name(package_name)
        req_path = path / Path(req_file)
        if not req_path.exists():
            # No requirements.txt: fall back to pyproject.toml. This is valid
            # only for a local/prebuilt deployment; remote build reads
            # requirements.txt, never pyproject.toml.
            if normalized_target in pyproject_dependency_names(path):
                if is_local_prebuilt_deployment(path, context):
                    return _create_result(
                        "pass",
                        f"Package '{package_name}' declared in pyproject.toml "
                        "(local/prebuilt deployment)",
                    )
                return _create_result(
                    "fail",
                    f"Package '{package_name}' is only declared in pyproject.toml; "
                    "Azure remote build installs from requirements.txt. Add it there "
                    "or deploy with a local/prebuilt build (--deployment-mode local).",
                )
            return _create_result(
                "fail",
                f"{req_path} not found and '{package_name}' not declared in pyproject.toml",
            )
        try:
            content = req_path.read_text(encoding="utf-8")
        except Exception as exc:
            return _handle_specific_exceptions(f"reading {req_file}", exc)
        normalized = _parse_requirements_names(content)
        declared = normalized_target in normalized
        if not declared and normalized_target in pyproject_dependency_names(path):
            if is_local_prebuilt_deployment(path, context):
                return _create_result(
                    "pass",
                    f"Package '{package_name}' declared in pyproject.toml "
                    "(local/prebuilt deployment)",
                )
            return _create_result(
                "fail",
                f"Package '{package_name}' is only declared in pyproject.toml; "
                "Azure remote build installs from requirements.txt. Add it there "
                "or deploy with a local/prebuilt build (--deployment-mode local).",
            )
        return _create_result(
            "pass" if declared else "fail",
            f"Package '{package_name}' {'declared' if declared else 'not declared'} in {req_file}",
        )

    @_rule_handler
    def _handle_package_forbidden(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Warn when a package that should NOT be pinned appears in requirements.txt."""
        condition = rule.get("condition", {}) or {}
        params = parse_package(condition)
        if params is None:
            return _create_result(
                "fail",
                "Missing 'package' in condition",
                file="requirements.txt",
            )
        package_name, req_file = params
        req_path = path / Path(req_file)
        if not req_path.exists():
            return _create_result("fail", f"{req_path} not found")
        try:
            content = req_path.read_text(encoding="utf-8")
        except Exception as exc:
            return _handle_specific_exceptions(f"reading {req_file}", exc)
        normalized = _parse_requirements_names(content)
        declared = canonicalize_name(package_name) in normalized
        if declared:
            return _create_result(
                "fail",
                f"Package '{package_name}' should not be declared in {req_file} "
                "(managed by the platform)",
            )
        return _create_result("pass", f"Package '{package_name}' not declared in {req_file}")

    @_rule_handler
    def _handle_native_dependency_risk(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Warn when requirements.txt includes packages with native extension risk."""
        condition = rule.get("condition", {}) or {}
        req_file_obj = condition.get("file", "requirements.txt")
        req_file = str(req_file_obj)
        req_path = path / Path(req_file)
        if not req_path.exists():
            return _create_result("skip", f"{req_file} not found; check skipped")
        try:
            content = req_path.read_text(encoding="utf-8")
        except Exception as exc:
            return _handle_specific_exceptions(f"reading {req_file}", exc)

        matches = _detect_native_dependency_risks(content)
        if not matches:
            return _create_result("pass", "No native dependency risk packages declared")

        matched_packages = ", ".join(package for package, _hint in matches)
        detail_lines = [
            f"Native dependencies detected: {matched_packages}",
            "These packages depend on platform-specific native libraries.",
            "Ensure your build environment matches the Azure Functions Linux runtime.",
            "Recommended: use remote build (`func azure functionapp publish --build remote`).",
        ]
        for package, hint in matches:
            if hint:
                detail_lines.append(f"- {package}: {hint}")
        return _create_result("fail", "\n".join(detail_lines))

    @_rule_handler
    def _handle_unpinned_requirements(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Warn when ``requirements.txt`` declares unpinned/unbounded dependencies.

        Azure remote build resolves ``requirements.txt`` at deploy time, so
        unpinned dependencies (no version specifier, or an open ``>=`` lower
        bound with no upper bound) make deployments non-reproducible and prone to
        surprise breakage.
        """
        condition = rule.get("condition", {}) or {}
        target = parse_target(condition) or "requirements.txt"
        req_path = path / target
        if not req_path.is_file():
            return _create_result("skip", f"{target} not found; unpinned check skipped")
        try:
            content = req_path.read_text(encoding="utf-8")
        except OSError as exc:
            return _handle_specific_exceptions(f"reading {target}", exc)
        unpinned: list[str] = []
        finding_lines: list[dict[str, object]] = []
        for line_no, raw in enumerate(content.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            try:
                requirement = Requirement(line)
            except InvalidRequirement:
                continue
            if requirement.url is not None:
                continue
            specifiers = list(requirement.specifier)
            if not specifiers:
                unpinned.append(f"- {requirement.name} (no version specifier)")
                finding_lines.append(
                    {
                        "file": target,
                        "line": line_no,
                        "message": f"{requirement.name} (no version specifier)",
                    }
                )
                continue
            has_upper_bound = any(
                spec.operator in ("==", "===", "~=", "<", "<=") for spec in specifiers
            )
            if not has_upper_bound:
                bounds = ",".join(str(spec) for spec in specifiers)
                unpinned.append(f"- {requirement.name} ({bounds}; no upper bound)")
                finding_lines.append(
                    {
                        "file": target,
                        "line": line_no,
                        "message": f"{requirement.name} ({bounds}; no upper bound)",
                    }
                )
        if not unpinned:
            return _create_result("pass", f"{target} dependencies are pinned/bounded")
        detail = "\n".join(
            [
                f"Unpinned or unbounded dependencies in {target}:",
                *unpinned[:10],
                "",
                "Fix: pin versions (e.g. 'package==1.2.3') or add an upper bound to "
                "keep deployments reproducible.",
            ]
        )
        return _create_result("fail", detail, file=target, locations=finding_lines[:10])
