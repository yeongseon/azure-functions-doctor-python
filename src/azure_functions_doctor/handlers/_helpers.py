import ast
from collections.abc import Callable, Iterable, Iterator
import contextvars
from fnmatch import fnmatch
from pathlib import Path
import re
import sys
from typing import (
    TYPE_CHECKING,
    Literal,
    NamedTuple,
    Optional,
    TypedDict,
    TypeVar,
)

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from azure_functions_doctor.inspection import (
    check_python_parser,
    read_inspection_json,
    read_inspection_text,
    read_inspection_toml,
)
from azure_functions_doctor.inspection_gaps import InspectionGap, record_gap
from azure_functions_doctor.logging_config import get_logger
from azure_functions_doctor.requirements_directives import parse_include_directive
from azure_functions_doctor.requirements_inspection import (
    iter_requirements_files,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from azure_functions_doctor.deploy_config import TargetConfig

EXCLUDED_PROJECT_DIRS = {
    # Python virtual environments
    ".venv",
    "venv",
    "env",
    ".env",
    # Installed packages / vendored dependencies
    "site-packages",
    "node_modules",
    # Build / packaging output
    "build",
    "dist",
    # Tooling caches
    ".pytest_cache",
    "__pycache__",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".ruff_cache",
    # Version control metadata
    ".git",
    ".hg",
    ".svn",
}


# Project-scoped extra exclude globs (issue #290). Populated from the
# ``[tool.azure-functions-doctor].exclude`` config and layered on top of
# ``EXCLUDED_PROJECT_DIRS``. Stored in a ``ContextVar`` so it stays scoped to
# the active diagnostic run without threading a parameter through every
# traversal helper. The tuple is ``(project_root, exclude_globs)``.
_extra_excludes: contextvars.ContextVar[tuple[Path, tuple[str, ...]]] = contextvars.ContextVar(
    "_extra_excludes", default=(Path(), ())
)


def set_extra_excludes(
    root: Path, globs: Iterable[str]
) -> contextvars.Token[tuple[Path, tuple[str, ...]]]:
    """Set the active extra-exclude globs and return a reset token."""
    normalized = tuple(g for g in globs if g)
    return _extra_excludes.set((root, normalized))


def reset_extra_excludes(
    token: contextvars.Token[tuple[Path, tuple[str, ...]]],
) -> None:
    """Restore the previous extra-exclude state."""
    _extra_excludes.reset(token)


def _matches_extra_exclude(candidate: Path) -> bool:
    """True when ``candidate`` matches a configured extra-exclude glob.

    Globs are matched against the candidate's POSIX path relative to the
    configured project root. A trailing-slash-free directory glob such as
    ``legacy`` also matches everything beneath it (``legacy/**``).
    """
    root, globs = _extra_excludes.get()
    if not globs:
        return False
    try:
        rel = candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    for glob in globs:
        pattern = glob.strip().rstrip("/")
        if not pattern:
            continue
        if fnmatch(rel, pattern) or fnmatch(rel, f"{pattern}/*"):
            return True
    return False


def _is_excluded_path(candidate: Path) -> bool:
    """True when ``candidate`` is under an excluded dir or an extra glob."""
    root, _ = _extra_excludes.get()
    try:
        relative_parts = candidate.resolve().relative_to(root.resolve()).parts
    except ValueError:
        relative_parts = candidate.parts
    if any(part in EXCLUDED_PROJECT_DIRS for part in relative_parts):
        return True
    return _matches_extra_exclude(candidate)


def iter_project_files(
    project_path: Path,
    patterns: str | tuple[str, ...] | list[str],
    *,
    include_default_excludes: bool = False,
) -> Iterator[Path]:
    """Single entry point for project file traversal (issue #393).

    Yields files under ``project_path`` matching ``patterns`` (rglob syntax),
    honoring ``EXCLUDED_PROJECT_DIRS`` by default and always honoring the user's
    ``[tool.azure-functions-doctor].exclude`` globs. Handlers must traverse
    through this helper instead of calling ``Path.rglob`` directly so
    extra excludes. Cleanup checks may request default-excluded paths explicitly;
    a regression test forbids raw rglob outside this module.
    """
    pattern_list: tuple[str, ...]
    if isinstance(patterns, str):
        pattern_list = (patterns,)
    else:
        pattern_list = tuple(patterns)
    for pattern in pattern_list:
        for candidate in sorted(project_path.rglob(pattern)):
            try:
                if not candidate.resolve().is_relative_to(project_path.resolve()):
                    record_gap(
                        InspectionGap(
                            candidate.absolute(),
                            1,
                            str(candidate.relative_to(project_path)),
                            "discovered file",
                        )
                    )
                    continue
            except (OSError, RuntimeError):
                continue
            if include_default_excludes:
                if not _matches_extra_exclude(candidate):
                    yield candidate
            elif not _is_excluded_path(candidate):
                yield candidate


class HandlerResult(TypedDict, total=False):
    status: str
    detail: str
    internal_error: str
    file: str
    line: int
    end_line: int
    column: int
    # Per-finding locations (issue #394/#395): each entry is a dict with
    # file/line/end_line/column/message keys; SARIF emits one result per entry.
    locations: list[dict[str, object]]
    # Finding Contract v2 (issue #348): optional auditable evidence a handler
    # may emit for date / compatibility findings.
    evidence: str
    expected: str
    actual: str
    source_url: str
    last_verified: str
    catalog_version: str
    # Per-finding severity / gate refinements (issue #343): a handler may WARN on
    # a retiring runtime but FAIL on an unsupported one, overriding the rule's
    # static severity/gate. Both are optional; when absent the rule defaults win.
    severity: str
    gate: bool


class RuleContext(TypedDict, total=False):
    target_python: str | None
    deployment_mode: str | None
    target_config: Optional["TargetConfig"]


# Platform-aware candidates for executables (for symmetric fallback)
_PYTHON_CANDIDATES: dict[str, list[str]] = {
    "python": ["python", "python3"] + (["py"] if sys.platform == "win32" else []),
    "python3": ["python3", "python"] + (["py"] if sys.platform == "win32" else []),
}

NATIVE_DEPENDENCY_PACKAGES: dict[str, str] = {
    "pyodbc": "requires unixODBC and a matching wheel",
    "cryptography": "verify OpenSSL-compatible wheels for the target runtime",
    "lxml": "ensure libxml2/libxslt-compatible wheels for Linux deployment",
    "pillow": "ensure libjpeg/zlib-compatible wheels for Linux deployment",
    "numpy": "ensure compiled wheels match the Azure Functions Linux runtime",
    "pandas": "ensure compiled wheels match the Azure Functions Linux runtime",
    "scipy": "ensure compiled wheels match the Azure Functions Linux runtime",
    "opencv-python": "ensure system-level native libraries match the target runtime",
    "psycopg2": "consider psycopg2-binary on Azure Functions Consumption plans",
    "grpcio": "ensure compiled wheels match the Azure Functions Linux runtime",
    "ujson": "ensure compiled wheels match the Azure Functions Linux runtime",
    "orjson": "ensure compiled wheels match the Azure Functions Linux runtime",
}


FUNCTION_APP_CONTAINERS = {
    "AsgiFunctionApp",
    "DFApp",
    "FunctionApp",
    "WsgiFunctionApp",
}

# Modules that may export Blueprint/FunctionApp-family constructors directly
# (``from azure.functions import FunctionApp as FA``), as opposed to the
# attribute-access form (``func.FunctionApp()``) which needs no alias
# resolution since the trailing attribute name is unaffected by how the
# module itself was imported.
_CONSTRUCTOR_SOURCE_MODULES = {"azure.functions", "azure.durable_functions"}


def _resolve_import_aliases(
    tree: ast.Module, target_names: set[str], modules: set[str] = _CONSTRUCTOR_SOURCE_MODULES
) -> dict[str, str]:
    """Map a local import alias back to the real name it refers to.

    Seeded with an identity mapping for every name in *target_names* (so a
    bare, un-aliased constructor name still matches even without an explicit
    import -- the pre-existing, intentionally permissive behavior), then
    resolves ``from <module> import <name> [as <alias>]`` where ``<module>``
    is one of *modules* and ``<name>`` is in *target_names*, so a bare
    ``ast.Name`` call site (e.g. ``FA()`` after
    ``from azure.functions import FunctionApp as FA``) can be recognized the
    same way an attribute call (``func.FunctionApp()``) already is,
    regardless of the import alias chosen (#446).
    """
    aliases: dict[str, str] = {name: name for name in target_names}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in modules:
            for alias in node.names:
                if alias.name in target_names:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


_LANGGRAPH_ADAPTER_MODULE = "azure_functions_langgraph"
_LANGGRAPH_ADAPTER_CLASS = "LangGraphApp"


def _source_contains_langgraph_functionapp_export(source: str) -> bool:
    """Return True for the documented toolkit composition pattern: import
    ``LangGraphApp`` from ``azure_functions_langgraph``, construct an
    instance, and export its real ``azure.functions.FunctionApp`` via the
    documented ``.function_app`` property (e.g. ``app = adapter.function_app``)
    (#590).

    Bounded static recognition only, deliberately stricter than
    :func:`_resolve_import_aliases` (which seeds an identity mapping for
    every target name so a bare SDK constructor name still matches without
    an import): ``LangGraphApp`` must actually be imported from
    ``azure_functions_langgraph`` here, or an unrelated local class/function
    of the same name would be misrecognized. The adapter instance must be
    locally constructed in this file, and the exported attribute access
    must be exactly ``.function_app`` on that instance -- never an
    arbitrary object's same-named attribute or a factory call.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == _LANGGRAPH_ADAPTER_MODULE:
            for alias in node.names:
                if alias.name == _LANGGRAPH_ADAPTER_CLASS:
                    imported_names.add(alias.asname or alias.name)
    if not imported_names:
        return False

    adapter_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func_node = node.value.func
            if isinstance(func_node, ast.Name) and func_node.id in imported_names:
                adapter_names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    if not adapter_names:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Attribute):
            exported = node.value
            if (
                exported.attr == "function_app"
                and isinstance(exported.value, ast.Name)
                and exported.value.id in adapter_names
            ):
                return True
    return False


def _discover_functionapp_aliases(source: str) -> set[str]:
    """Extract variable names assigned a supported app container or ``Blueprint()`` call.

    Scans AST assignments like ``app = func.FunctionApp()`` and
    ``bp = Blueprint()`` to discover alias names used for decorators.
    Returns the set of discovered names, or ``{"app"}`` when none are found.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"app"}

    target_attrs = FUNCTION_APP_CONTAINERS | {"Blueprint"}
    import_aliases = _resolve_import_aliases(tree, target_attrs)

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func_node = node.value.func
            attr_name: str | None = None
            if isinstance(func_node, ast.Attribute):
                attr_name = func_node.attr
            elif isinstance(func_node, ast.Name):
                attr_name = import_aliases.get(func_node.id, func_node.id)
            if attr_name in target_attrs:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
    return names or {"app"}


def _collect_blueprint_aliases(source: str) -> set[str]:
    """Extract variable names assigned a ``Blueprint()`` call."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    import_aliases = _resolve_import_aliases(tree, {"Blueprint"})
    module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module_names.update(
                alias.asname
                for alias in node.names
                if alias.name == "azure.functions" and alias.asname is not None
            )

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func_node = node.value.func
            is_constructor = (
                isinstance(func_node, ast.Name) and func_node.id in import_aliases
            ) or (
                isinstance(func_node, ast.Attribute)
                and func_node.attr == "Blueprint"
                and isinstance(func_node.value, ast.Name)
                and func_node.value.id in module_names
            )
            if not is_constructor:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _collect_register_functions_args(source: str) -> set[str]:
    """Collect Blueprint aliases passed to ``register_functions(...)`` calls.

    Only calls on a discovered FunctionApp-family instance are recognized
    (any of ``FUNCTION_APP_CONTAINERS``, including ``DFApp`` -- #446 --, not
    only ``FunctionApp``).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    import_aliases = _resolve_import_aliases(tree, FUNCTION_APP_CONTAINERS)
    module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module_names.update(
                alias.asname
                for alias in node.names
                if alias.name in _CONSTRUCTOR_SOURCE_MODULES and alias.asname is not None
            )

    app_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func_node = node.value.func
        is_constructor = (isinstance(func_node, ast.Name) and func_node.id in import_aliases) or (
            isinstance(func_node, ast.Attribute)
            and func_node.attr in FUNCTION_APP_CONTAINERS
            and isinstance(func_node.value, ast.Name)
            and func_node.value.id in module_names
        )
        if is_constructor:
            app_names.update(target.id for target in node.targets if isinstance(target, ast.Name))

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func_node = node.func
        if not isinstance(func_node, ast.Attribute):
            continue
        if func_node.attr not in {"register_blueprint", "register_functions"}:
            continue
        if not isinstance(func_node.value, ast.Name) or func_node.value.id not in app_names:
            continue

        for arg in node.args:
            if isinstance(arg, ast.Name):
                names.add(arg.id)
    return names


def _source_contains_blueprint_decorator(source: str, blueprint_aliases: set[str]) -> set[str]:
    """Return Blueprint aliases used in decorators like ``@bp.route()``."""
    if not blueprint_aliases:
        return set()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    matched_aliases: set[str] = set()

    def decorator_alias(dec: ast.expr) -> str | None:
        node: ast.expr = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            alias = node.value.id
            if alias in blueprint_aliases:
                return alias
        return None

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.decorator_list
        ):
            for dec in node.decorator_list:
                alias = decorator_alias(dec)
                if alias is not None:
                    matched_aliases.add(alias)
    return matched_aliases


def _resolve_project_module_path(
    importer_file: Path, project_root: Path, module: str, level: int
) -> Path | None:
    """Resolve an import's module name to a project-local ``.py`` file path.

    Bounded: handles absolute dotted module imports (``import first``,
    ``from first import bp``) resolved from *project_root*, and relative
    imports (``from .first import bp``) resolved from *importer_file*'s
    directory. Returns ``None`` when the module isn't a local project file
    (e.g. a third-party package) -- only statically resolvable project-local
    modules participate in cross-file Blueprint identity resolution (#446);
    dynamic imports are out of scope, matching this handler's existing
    static-analysis-only design.
    """
    if level == 0:
        if not module:
            return None
        parts = module.split(".")
        base = project_root
    else:
        base = importer_file.parent
        for _ in range(level - 1):
            base = base.parent
        parts = module.split(".") if module else []

    if not parts:
        return None
    candidate = base.joinpath(*parts).with_suffix(".py")
    if candidate.is_file():
        return candidate
    candidate_pkg = base.joinpath(*parts, "__init__.py")
    if candidate_pkg.is_file():
        return candidate_pkg
    return None


def _collect_unregistered_blueprint_aliases(path: Path) -> set[str]:
    """Collect Blueprint aliases that are decorated but never registered.

    Tracks module-qualified identity -- (source file, local name) -- through
    discovery, import resolution, and registration matching, so two distinct
    ``Blueprint()`` instances that happen to share a bare local name across
    files (e.g. ``bp`` in both ``first.py`` and ``second.py``) are never
    conflated: registering one must never be treated as registering the
    other (#446). A registration argument is resolved back to its defining
    file by following project-local ``from <module> import <name> [as
    <alias>]`` re-exports; a name with no statically resolvable origin is
    treated as not registered, matching this handler's existing
    static-analysis-only scope (no dynamic imports or wildcard resolution).
    """
    project_contents = list(_iter_project_py_contents(path))
    contents_by_file: dict[Path, str] = dict(project_contents)

    parsed: dict[Path, ast.Module] = {}
    for py_file, content in project_contents:
        try:
            parsed[py_file] = ast.parse(content)
        except SyntaxError:
            continue

    file_blueprints: dict[Path, set[str]] = {}
    file_receivers: dict[Path, set[str]] = {}
    file_imports: dict[Path, dict[str, tuple[Path, str]]] = {}

    for py_file, tree in parsed.items():
        bp_import_aliases = _resolve_import_aliases(tree, {"Blueprint"})
        app_import_aliases = _resolve_import_aliases(tree, FUNCTION_APP_CONTAINERS)
        module_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                module_names.update(
                    alias.asname
                    for alias in node.names
                    if alias.name in _CONSTRUCTOR_SOURCE_MODULES and alias.asname is not None
                )

        local_blueprints: set[str] = set()
        local_receivers: set[str] = set()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
                continue
            func_node = node.value.func
            is_blueprint = (
                isinstance(func_node, ast.Name) and func_node.id in bp_import_aliases
            ) or (
                isinstance(func_node, ast.Attribute)
                and func_node.attr == "Blueprint"
                and isinstance(func_node.value, ast.Name)
                and func_node.value.id in module_names
            )
            is_receiver = (
                isinstance(func_node, ast.Name) and func_node.id in app_import_aliases
            ) or (
                isinstance(func_node, ast.Attribute)
                and func_node.attr in FUNCTION_APP_CONTAINERS
                and isinstance(func_node.value, ast.Name)
                and func_node.value.id in module_names
            )
            if is_blueprint:
                local_blueprints.update(t.id for t in node.targets if isinstance(t, ast.Name))
            elif is_receiver:
                local_receivers.update(t.id for t in node.targets if isinstance(t, ast.Name))

        file_blueprints[py_file] = local_blueprints
        file_receivers[py_file] = local_receivers

        imports: dict[str, tuple[Path, str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                origin = _resolve_project_module_path(py_file, path, node.module or "", node.level)
                if origin is None or origin not in parsed:
                    continue
                for alias in node.names:
                    imports[alias.asname or alias.name] = (origin, alias.name)
        file_imports[py_file] = imports

    def _resolve_to_blueprint_identity(
        file: Path, name: str, _seen: frozenset[tuple[Path, str]] = frozenset()
    ) -> tuple[Path, str] | None:
        key = (file, name)
        if key in _seen:
            return None
        if name in file_blueprints.get(file, set()):
            return key
        origin = file_imports.get(file, {}).get(name)
        if origin is None:
            return None
        origin_file, origin_name = origin
        return _resolve_to_blueprint_identity(origin_file, origin_name, _seen | {key})

    decorated: set[tuple[Path, str]] = set()
    registered: set[tuple[Path, str]] = set()

    for py_file, tree in parsed.items():
        local_blueprints = file_blueprints[py_file]
        decorated_names = _source_contains_blueprint_decorator(
            contents_by_file[py_file], local_blueprints
        )
        for name in decorated_names:
            decorated.add((py_file, name))

        local_receivers = file_receivers[py_file]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_node = node.func
            if not isinstance(func_node, ast.Attribute):
                continue
            if func_node.attr not in {"register_blueprint", "register_functions"}:
                continue
            if (
                not isinstance(func_node.value, ast.Name)
                or func_node.value.id not in local_receivers
            ):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    identity = _resolve_to_blueprint_identity(py_file, arg.id)
                    if identity is not None:
                        registered.add(identity)

    unregistered = decorated - registered
    return {name for _file, name in unregistered}


def _decorator_simple_name(dec: ast.expr) -> str | None:
    """Extract the leaf name of a decorator.

    Handles bare ``@name``, attribute ``@mod.name`` and call ``@mod.name(...)``
    forms, returning the final identifier (``name``) or ``None`` when the
    decorator has no simple name (e.g. subscripts).
    """
    node: ast.expr = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _validate_http_above_binding(
    node: ast.FunctionDef | ast.AsyncFunctionDef, app_aliases: set[str]
) -> bool:
    """Return True when ``@validate_http`` sits above an ``@app.<binding>`` decorator.

    ``decorator_list`` index 0 is the topmost/outermost decorator. When
    ``@validate_http`` has a lower index than any Azure Functions binding
    decorator (an ``@<app>.<name>`` attribute call on a discovered FunctionApp
    alias), it wraps the SDK ``FunctionBuilder`` instead of the handler and is
    therefore inactive.
    """
    validate_idx: int | None = None
    binding_indices: list[int] = []
    for i, dec in enumerate(node.decorator_list):
        if validate_idx is None and _decorator_simple_name(dec) == "validate_http":
            validate_idx = i
        inner: ast.expr = dec.func if isinstance(dec, ast.Call) else dec
        if (
            isinstance(inner, ast.Attribute)
            and isinstance(inner.value, ast.Name)
            and inner.value.id in app_aliases
        ):
            binding_indices.append(i)
    if validate_idx is None or not binding_indices:
        return False
    return any(validate_idx < binding_idx for binding_idx in binding_indices)


def _collect_inverted_decorator_order(
    path: Path, expected_order: list[str]
) -> list[tuple[str, int]]:
    """Return "(file:function, lineno)" pairs whose decorators violate *expected_order*.

    *expected_order* lists decorator leaf names from **outermost to innermost**
    (the intended top-to-bottom stacking). For the validation/logging pairing
    that is ``["with_context", "validate_http"]`` (``@with_context`` above
    ``@validate_http``). In ``decorator_list`` index 0 is the topmost/outermost
    decorator, so the expected names must appear in the same relative order. A
    function is flagged when two or more of the expected decorators are present
    but their actual relative order does not match *expected_order*.
    A function is also flagged when ``@validate_http`` appears *above* (outer to)
    any Azure Functions binding decorator (e.g. ``@app.route``,
    ``@app.durable_client_input``). In that order ``@validate_http`` receives an
    SDK ``FunctionBuilder`` instead of the handler, so validation is inactive and
    no endpoint metadata is emitted -- a silent "dead handler".
    """
    inverted: list[tuple[str, int]] = []
    for py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        app_aliases = _discover_functionapp_aliases(content)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.decorator_list:
                continue
            positions: dict[str, int] = {}
            for i, dec in enumerate(node.decorator_list):
                name = _decorator_simple_name(dec)
                if name in expected_order and name not in positions:
                    positions[name] = i
            present = [name for name in expected_order if name in positions]
            label = f"{py_file.relative_to(path)}:{node.name}"
            if len(present) >= 2:
                actual = sorted(present, key=lambda name: positions[name])
                if actual != present:
                    inverted.append((label, node.decorator_list[0].lineno))
                    continue
            if _validate_http_above_binding(node, app_aliases):
                inverted.append((label, node.decorator_list[0].lineno))
    return inverted


def _project_declares_openapi_dep(path: Path) -> bool:
    """Return True when ``azure-functions-openapi`` is declared in
    ``requirements.txt``. Missing/unreadable file counts as not declared; the
    scan-before-spec and version-mixing rules are meaningless without it
    (generic ``build``/``create_spec`` call names belong to other libraries).
    """
    req_path = path / "requirements.txt"
    if not req_path.exists():
        return False
    content = _read_project_python_file(req_path)
    if content is None:
        return False
    return canonicalize_name("azure-functions-openapi") in _parse_requirements_names(
        content, req_path
    )


def _project_declares_validation_dep(path: Path) -> bool:
    """Return True when ``azure-functions-validation`` is declared in
    ``requirements.txt``. Missing or unreadable file counts as not declared.
    """
    req_path = path / "requirements.txt"
    if not req_path.exists():
        return False
    content = _read_project_python_file(req_path)
    if content is None:
        return False
    return canonicalize_name("azure-functions-validation") in _parse_requirements_names(
        content, req_path
    )


_SPEC_SERVING_CALL_NAMES: frozenset[str] = frozenset(
    {
        "get_openapi_json",
        "get_openapi_yaml",
        "get_openapi_spec",
        "generate_openapi_spec",
        "generate_openapi_report",
        "render_swagger_ui",
        "get_swagger_ui_html",
        "swagger_ui_html",
    }
)


def _is_spec_serving_handler(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True when a route handler serves the OpenAPI document / Swagger UI.

    Such handlers (e.g. returning ``get_openapi_json`` / ``get_openapi_yaml`` or
    rendering Swagger UI) expose static spec content and intentionally carry no
    ``@validate_http``; flagging them for missing endpoint metadata is a false
    positive.
    """
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _dotted_call_name(child.func)
        if name is None:
            continue
        if name.rsplit(".", 1)[-1] in _SPEC_SERVING_CALL_NAMES:
            return True
    return False


# Decorators that emit OpenAPI endpoint metadata other than ``@validate_http``.
# A route carrying any of these is considered metadata-covered and is not
# flagged for missing endpoint metadata.
_ENDPOINT_METADATA_DECORATORS = frozenset({"openapi", "openapi_metadata", "langgraph_metadata"})


def _collect_routes_missing_validate_http_locations(
    path: Path,
) -> list[tuple[str, int, int | None, int]]:
    """Return ``(label, lineno)`` pairs for HTTP route handlers that expose no
    endpoint OpenAPI metadata.

    A handler is considered *covered* when it carries an *active* ``@validate_http``
    or any other supported endpoint-metadata decorator (e.g. ``@openapi`` or the
    LangGraph metadata decorators); such handlers are omitted from the result.

    ``label`` is ``"file:function"`` and ``lineno`` is the 1-based source line of
    the offending function definition.

    ``@validate_http`` only covers a handler when it is applied *below* (inner to)
    the ``@app.route`` decorator. When it appears above the route decorator it
    wraps the SDK ``FunctionBuilder``, so validation and endpoint metadata are
    inactive even though the decorator name is present.
    """
    uncovered: list[tuple[str, int, int | None, int]] = []
    for py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        app_aliases = _discover_functionapp_aliases(content)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.decorator_list:
                continue
            is_route = False
            route_idx: int | None = None
            validate_idx: int | None = None
            has_other_metadata = False
            for i, dec in enumerate(node.decorator_list):
                inner: ast.expr = dec.func if isinstance(dec, ast.Call) else dec
                if (
                    isinstance(inner, ast.Attribute)
                    and inner.attr == "route"
                    and isinstance(inner.value, ast.Name)
                    and inner.value.id in app_aliases
                ):
                    is_route = True
                    if route_idx is None:
                        route_idx = i
                if validate_idx is None and _decorator_simple_name(dec) == "validate_http":
                    validate_idx = i
                if _decorator_simple_name(dec) in _ENDPOINT_METADATA_DECORATORS:
                    has_other_metadata = True
            has_active_validate_http = (
                validate_idx is not None and route_idx is not None and validate_idx > route_idx
            )
            covered = has_active_validate_http or has_other_metadata
            if is_route and not covered and not _is_spec_serving_handler(node):
                uncovered.append(
                    (
                        f"{py_file.relative_to(path)}:{node.name}",
                        node.lineno,
                        node.end_lineno,
                        node.col_offset + 1,
                    )
                )
    return uncovered


def _collect_routes_missing_validate_http(path: Path) -> list[str]:
    """Return "file:function" labels for HTTP route handlers that lack an
    *active* ``@validate_http`` and therefore emit no endpoint OpenAPI metadata.

    Thin string-only wrapper over
    :func:`_collect_routes_missing_validate_http_locations`.
    """
    return [lbl for lbl, _ln, _end, _col in _collect_routes_missing_validate_http_locations(path)]


def _dotted_call_name(func: ast.expr) -> str | None:
    """Return the dotted name of a call target, or ``None``.

    Walks an ``ast.Attribute`` chain down to a root ``ast.Name`` and rebuilds
    the dotted path (e.g. ``datetime.datetime.now`` -> ``"datetime.datetime.now"``,
    ``random.randint`` -> ``"random.randint"``, bare ``open`` -> ``"open"``).
    Returns ``None`` when the call target is not a simple name/attribute chain
    (e.g. a subscript or call result).
    """
    parts: list[str] = []
    node: ast.expr = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _collect_openapi_version_mixing(path: Path) -> dict[str, set[str]]:
    """Return a mapping of OpenAPI ``major.minor`` version -> signals found.

    Recognised keys are ``"3.0"``, ``"3.1"`` and ``"3.2"``. Signals are string
    constants like ``3.0.N`` / ``3.1.N`` / ``3.2.N``; a ``nullable`` keyword
    argument is a 3.0-only signal (``nullable`` was removed in OpenAPI 3.1+).
    Callers treat two or more populated version keys as a version-mixing warning,
    so a single-version project (including 3.2-only) never warns.
    """
    signals: dict[str, set[str]] = {"3.0": set(), "3.1": set(), "3.2": set()}
    version_re = re.compile(r"^3\.(0|1|2)\.\d+$")
    for _py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                match = version_re.match(node.value)
                if match is not None:
                    signals[f"3.{match.group(1)}"].add(node.value)
            elif isinstance(node, ast.keyword) and node.arg == "nullable":
                signals["3.0"].add("nullable")
    return signals


def _collect_scan_before_spec(
    path: Path, scan_names: set[str], spec_names: set[str]
) -> tuple[list[str], list[tuple[str, int]]]:
    """Return "file:spec_call" labels where a spec build precedes endpoint scan.

    For each file, records the line numbers of scan-style calls and spec-style
    calls (matched by simple call name). A violation is a spec call whose line
    precedes the earliest scan call in that file. Additionally, if spec calls
    exist anywhere in the project but no scan call is ever seen, every spec call
    is reported (scanning was skipped entirely).

    Returns ``(labels, located)`` where ``located`` carries ``(label, lineno)``
    pairs so callers can emit per-line SARIF locations (issue #394).
    """
    violations: list[str] = []
    located: list[tuple[str, int]] = []
    all_spec_located: list[tuple[str, int]] = []
    any_scan_seen = False
    spec_labels: list[str] = []
    for py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        scan_lines: list[int] = []
        spec_calls: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _dotted_call_name(node.func)
            if name is None:
                continue
            leaf = name.rsplit(".", 1)[-1]
            if leaf in scan_names:
                scan_lines.append(node.lineno)
            elif leaf in spec_names:
                spec_calls.append((node.lineno, leaf))
        for lineno, leaf in spec_calls:
            label = f"{py_file.relative_to(path)}:{leaf}"
            spec_labels.append(label)
            all_spec_located.append((label, lineno))
        if scan_lines:
            any_scan_seen = True
            first_scan = min(scan_lines)
            for lineno, leaf in spec_calls:
                if lineno < first_scan:
                    label = f"{py_file.relative_to(path)}:{leaf}"
                    violations.append(label)
                    located.append((label, lineno))
    if spec_labels and not any_scan_seen:
        # Scanning was skipped entirely: every spec call is a violation.
        return spec_labels, all_spec_located
    return violations, located


def _project_imports_langgraph(path: Path) -> bool:
    """Return True when any project module imports ``langgraph``."""
    for _py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "langgraph" or alias.name.startswith("langgraph."):
                        return True
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == "langgraph" or mod.startswith("langgraph."):
                    return True
    return False


def _collect_anonymous_auth_routes(
    path: Path, flag_missing_auth_level: bool = False
) -> list[tuple[str, int]]:
    """Return "(file:function, lineno)" pairs for routes using anonymous auth.

    A route is flagged when a decorator keyword ``auth_level`` resolves to
    ``AuthLevel.ANONYMOUS`` (an attribute whose leaf is ``ANONYMOUS``) or to the
    string ``"anonymous"`` (case-insensitive). When *flag_missing_auth_level* is
    True, routes without any ``auth_level`` keyword are also reported.
    """
    flagged: list[tuple[str, int]] = []
    for py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        app_aliases = _discover_functionapp_aliases(content)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                inner = dec.func
                if not (
                    isinstance(inner, ast.Attribute)
                    and inner.attr == "route"
                    and isinstance(inner.value, ast.Name)
                    and inner.value.id in app_aliases
                ):
                    continue
                auth_kw = None
                for kw in dec.keywords:
                    if kw.arg == "auth_level":
                        auth_kw = kw.value
                        break
                label = f"{py_file.relative_to(path)}:{node.name}"
                if auth_kw is None:
                    if flag_missing_auth_level:
                        flagged.append((label, dec.lineno))
                    continue
                if isinstance(auth_kw, ast.Attribute) and auth_kw.attr == "ANONYMOUS":
                    flagged.append((label, dec.lineno))
                elif (
                    isinstance(auth_kw, ast.Constant)
                    and isinstance(auth_kw.value, str)
                    and auth_kw.value.lower() == "anonymous"
                ):
                    flagged.append((label, dec.lineno))
    return flagged


def _collect_binding_connections(path: Path) -> list[tuple[str, str, int]]:
    """Return ``(connection_name, "file:function", lineno)`` triples for v2 binding decorators.

    Scans decorators applied to a discovered ``FunctionApp``/``Blueprint`` alias for a
    ``connection="..."`` keyword and collects the referenced setting name. Only
    string-literal connection names are collected; dynamic expressions (variables,
    ``os.environ[...]``) cannot be resolved statically and are skipped. This covers
    Storage, Service Bus, Event Hub, Cosmos DB and any other binding that exposes a
    ``connection`` keyword, without hard-coding a decorator whitelist.
    """
    references: list[tuple[str, str, int]] = []
    for py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        app_aliases = _discover_functionapp_aliases(content)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                inner = dec.func
                if not (
                    isinstance(inner, ast.Attribute)
                    and isinstance(inner.value, ast.Name)
                    and inner.value.id in app_aliases
                ):
                    continue
                for kw in dec.keywords:
                    if kw.arg != "connection":
                        continue
                    if (
                        isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                        and kw.value.value.strip()
                    ):
                        label = f"{py_file.relative_to(path)}:{node.name}"
                        references.append((kw.value.value, label, dec.lineno))
    return references


def _project_activates_trace_context(path: Path) -> list[str]:
    """Return "file:location" labels where the project explicitly opts into
    ``azure-functions-logging`` OTel trace-context activation.

    Two activation signals are detected:

    * a keyword ``activate_trace_context=True`` on any call (e.g.
      ``setup_logging(activate_trace_context=True)`` or
      ``logging_context(..., activate_trace_context=True)``); and
    * a call to ``set_default_trace_context_activation(True)`` (matched by the
      dotted-call leaf name, with a truthy first positional or keyword arg).
    """
    activations: list[str] = []
    for py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        label_base = str(py_file.relative_to(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (
                    kw.arg == "activate_trace_context"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    activations.append(f"{label_base}:{node.lineno}")
                    break
            leaf = _dotted_call_name(node.func)
            if leaf is not None and leaf.rsplit(".", 1)[-1] == (
                "set_default_trace_context_activation"
            ):
                enabled = _first_call_arg_is_true(node)
                if enabled:
                    activations.append(f"{label_base}:{node.lineno}")
    return activations


def _first_call_arg_is_true(node: ast.Call) -> bool:
    """Return True when a call's first positional (or ``enabled`` keyword) arg is the
    literal ``True``. A bare call with no args is treated as enabling activation.
    """
    if node.args:
        first = node.args[0]
        return isinstance(first, ast.Constant) and first.value is True
    for kw in node.keywords:
        if kw.arg == "enabled":
            return isinstance(kw.value, ast.Constant) and kw.value.value is True
    return not node.keywords


_KNOWN_OTEL_EXTRA_PACKAGES = {"azure-functions-logging"}


def _pyproject_dependency_specs(path: Path) -> list[str]:
    """Return raw dependency specifier strings from pyproject.toml, with
    extras markers intact (unlike :func:`pyproject_dependency_names`, which
    discards them after canonicalizing the bare name)."""
    data = _load_pyproject(path)
    if not data:
        return []
    project = data.get("project")
    if not isinstance(project, dict):
        return []
    specs: list[str] = []
    deps = project.get("dependencies")
    if isinstance(deps, list):
        specs.extend(str(item) for item in deps)
    optional = project.get("optional-dependencies")
    if isinstance(optional, dict):
        for group in optional.values():
            if isinstance(group, list):
                specs.extend(str(item) for item in group)
    return specs


def _declares_known_otel_extra(path: Path) -> bool:
    """Return True when the project declares a known package's ``otel`` extra
    (currently ``azure-functions-logging[otel]``) in requirements.txt or
    pyproject.toml.

    This is a hardcoded, known declared-extra relationship -- installed
    ``azure-functions-logging`` metadata declares
    ``opentelemetry-api>=1.24; extra == 'otel'`` -- recognized offline from
    the parsed specifier alone, not a resolution of arbitrary transitive
    dependencies or an inspection of installed packages (#586).
    """
    specs: list[str] = list(_pyproject_dependency_specs(path))
    req_path = path / "requirements.txt"
    if req_path.exists():
        content = _read_project_python_file(req_path)
        if content is not None:
            specs.extend(
                line
                for line in _iter_requirements_txt_lines(content, req_path)
                if not (line.startswith("-e ") or line.startswith("--editable"))
            )
    for spec in specs:
        try:
            req = Requirement(spec)
        except InvalidRequirement:
            continue
        if canonicalize_name(req.name) in _KNOWN_OTEL_EXTRA_PACKAGES and "otel" in {
            extra.lower() for extra in req.extras
        }:
            return True
    return False


def _project_declares_opentelemetry(path: Path) -> bool:
    """Return True when the project declares any ``opentelemetry`` distribution in
    ``requirements.txt`` or ``pyproject.toml`` (runtime or optional dependencies),
    or a known package's declared ``otel`` extra that pulls one in transitively.

    The ``azure-functions-logging[otel]`` extra pulls in ``opentelemetry-api``, so
    any declared ``opentelemetry-*`` package -- or the ``azure-functions-logging``
    ``otel`` extra itself (#586) -- satisfies the activation requirement.
    """
    declared: set[str] = set(pyproject_dependency_names(path))
    req_path = path / "requirements.txt"
    if req_path.exists():
        content = _read_project_python_file(req_path)
        if content is not None:
            declared |= _parse_requirements_names(content, req_path)
    if any(name.startswith("opentelemetry") for name in declared):
        return True
    return _declares_known_otel_extra(path)


def _collect_orchestrator_nondeterminism(
    path: Path, blocklist: set[str], decorator_names: set[str]
) -> list[tuple[str, int]]:
    """Return "(file:function -> call, lineno)" pairs for nondeterministic calls.

    Finds functions decorated with any name in *decorator_names* (matched by
    decorator leaf name, e.g. ``orchestration_trigger``) and reports calls whose
    dotted name matches an entry in *blocklist* either exactly or as a dotted
    suffix (``endswith("." + entry)``).
    """
    flagged: list[tuple[str, int]] = []
    for py_file, content in _iter_project_py_contents(path):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            dec_names = {_decorator_simple_name(d) for d in node.decorator_list}
            if dec_names.isdisjoint(decorator_names):
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                dotted = _dotted_call_name(sub.func)
                if dotted is None:
                    continue
                for entry in blocklist:
                    if dotted == entry or dotted.endswith("." + entry):
                        flagged.append(
                            (f"{py_file.relative_to(path)}:{node.name} -> {dotted}", sub.lineno)
                        )
                        break
    return flagged


def _collect_unsupported_metadata_versions(
    path: Path,
    files: list[str],
    fields: list[str],
    supported: list[str],
) -> list[tuple[str, str]]:
    """Return (source, version) tuples for metadata versions outside *supported*.

    Reads ``extensionBundle.version`` from ``host.json`` plus any files matched
    by the *files* globs, looking up each name in *fields* (e.g.
    ``metadataVersion``). A version is reported when it is not present in
    *supported*. Malformed or unreadable JSON is silently skipped.
    """
    found: list[tuple[str, str]] = []
    supported_set = set(supported)

    def _load(p: Path) -> object:
        try:
            return read_inspection_json(p)
        except (OSError, ValueError, UnicodeDecodeError):
            return None

    host_json = path / "host.json"
    if host_json.exists():
        data = _load(host_json)
        bundle = _resolve_host_json_path(data, "$.extensionBundle.version")
        if isinstance(bundle, str) and bundle not in supported_set:
            found.append(("host.json:extensionBundle.version", bundle))

    seen: set[Path] = set()
    for pattern in files:
        for match in iter_project_files(path, pattern):
            if match in seen or _is_excluded_path(match):
                continue
            seen.add(match)
            data = _load(match)
            if not isinstance(data, dict):
                continue
            for field in fields:
                value = data.get(field)
                if isinstance(value, str) and value not in supported_set:
                    found.append((f"{match.relative_to(path)}:{field}", value))
    return found


def _source_contains_ast(source: str, identifier: str) -> bool:
    """Return True when the source contains a decorator like ``@identifier.xxx``.

    ``identifier`` may be a pipe-separated list (e.g. ``"app|bp"``) to match
    any of the given names, which covers both ``@app.route()`` and the
    Blueprint-style ``@bp.route()``.

    Additionally, ``FunctionApp()`` and ``Blueprint()`` variable assignments are
    discovered automatically so that custom aliases (e.g. ``fa = func.FunctionApp()``)
    are recognised even when they are not listed in ``identifier``.
    """
    identifiers = set(identifier.split("|"))
    # Merge in dynamically-discovered aliases
    identifiers |= _discover_functionapp_aliases(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    def decorator_matches(dec: ast.expr) -> bool:
        # @app.route() is ast.Call(func=Attribute(...)); @app.route is ast.Attribute
        node: ast.expr = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return node.value.id in identifiers
        return False

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.decorator_list
        ):
            for dec in node.decorator_list:
                if decorator_matches(dec):
                    return True
    # The documented LangGraph adapter composition exports a real
    # FunctionApp through a property, never a decorator on a locally
    # defined handler, so a project using only that pattern has no
    # decorator for the loop above to find; it is recognized directly
    # instead of being misreported as missing v2 signals (#590).
    return _source_contains_langgraph_functionapp_export(source)


def _iter_project_py_contents(path: Path) -> Iterator[tuple[Path, str]]:
    """Yield (py_file, content) for each .py file under path, skipping excluded dirs."""
    for py_file in iter_project_files(path, "*.py"):
        content = _read_project_python_file(py_file)
        if content is None:
            continue
        yield py_file, content


def _read_project_python_file(py_file: Path) -> str | None:
    """Read Python source without failing the whole traversal."""
    try:
        if py_file.name == "requirements.txt" and py_file.is_symlink():
            return None
        content = read_inspection_text(py_file, universal_newlines=False)
        if py_file.suffix == ".py":
            check_python_parser(content, py_file)
        return content
    except PermissionError:
        logger.warning("Permission denied reading source")
        return None
    except (MemoryError, OSError, ValueError) as exc:
        logger.debug("Skip unreadable source (%s)", type(exc).__name__)
        return None


def _iter_requirements_txt_lines(content: str, source_path: Path | None = None) -> list[str]:
    """Yield cleaned requirement-spec lines from requirements.txt content,
    including editable-install lines unmodified.

    Shared by :func:`_parse_requirements_names` and the OpenTelemetry-extra
    check (#586): follows ``-r``/``--requirement`` includes recursively (same
    depth/cycle guards), skips other pip flags and comments, but -- unlike
    ``_parse_requirements_names``'s final name set -- preserves each line's
    extras marker (``pkg[extra]``) instead of discarding it, since
    recognizing a known package's declared extra requires the extras, not
    just its name.
    """
    contents = (
        [text.removeprefix("\ufeff") for _, text in iter_requirements_files(source_path, content)]
        if source_path is not None
        else [content.removeprefix("\ufeff")]
    )

    lines: list[str] = []
    for requirements_content in contents:
        for raw_line in requirements_content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("-r ", "-c ", "--requirement", "--constraint")):
                continue
            if line.startswith("-e ") or line.startswith("--editable"):
                lines.append(line)
                continue
            if line.startswith("-"):
                continue
            line = line.split("#")[0].strip()
            if line:
                lines.append(line)
    return lines


def _parse_requirements_names(content: str, source_path: Path | None = None) -> set[str]:
    """Extract normalized package names from requirements.txt content.

    Handles extras (``requests[security]``), environment markers (``;``),
    URL installs (``@``), pip directives (``-r``, ``-e``), and inline comments.
    """
    names: set[str] = set()
    for line in _iter_requirements_txt_lines(content, source_path):
        if line.startswith("-e ") or line.startswith("--editable"):
            egg_match = re.search(r"#egg=([^&\s]+)", line)
            if egg_match:
                names.add(canonicalize_name(egg_match.group(1)))
            continue
        try:
            req = Requirement(line)
            names.add(canonicalize_name(req.name))
        except InvalidRequirement:
            # Fall back to a simple split for unparseable lines
            name = re.split(r"[=<>!~;\[\]@]", line, maxsplit=1)[0].strip()
            if name:
                names.add(canonicalize_name(name))
    return names


def _load_pyproject(path: Path) -> dict[str, object] | None:
    """Load and parse ``pyproject.toml`` from ``path``.

    Returns the parsed table, or ``None`` when the file is absent, unreadable,
    or not valid TOML.
    """
    pyproject_path = path / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    try:
        return dict(read_inspection_toml(pyproject_path))
    except (OSError, ValueError) as exc:
        logger.debug("Skip pyproject.toml (%s)", type(exc).__name__)
        return None


def pyproject_dependency_names(path: Path) -> set[str]:
    """Return canonicalized dependency names declared in ``pyproject.toml``.

    Collects names from ``[project].dependencies`` and every
    ``[project.optional-dependencies]`` group. Unparseable specifiers are
    skipped. Returns an empty set when no manifest or dependencies exist.
    """
    data = _load_pyproject(path)
    if not data:
        return set()
    project = data.get("project")
    if not isinstance(project, dict):
        return set()
    specs: list[str] = []
    deps = project.get("dependencies")
    if isinstance(deps, list):
        specs.extend(str(item) for item in deps)
    optional = project.get("optional-dependencies")
    if isinstance(optional, dict):
        for group in optional.values():
            if isinstance(group, list):
                specs.extend(str(item) for item in group)
    names: set[str] = set()
    for spec in specs:
        try:
            names.add(canonicalize_name(Requirement(spec).name))
        except InvalidRequirement:
            continue
    return names


class DoctorConfig(TypedDict):
    """Resolved ``[tool.azure-functions-doctor]`` project configuration."""

    ignore: list[str]
    exclude: list[str]


def load_doctor_config(path: Path) -> DoctorConfig:
    """Load ``[tool.azure-functions-doctor]`` settings from ``pyproject.toml``.

    Returns ``ignore`` (rule ids to suppress and report as ``skip``) and
    ``exclude`` (extra path globs layered on top of ``EXCLUDED_PROJECT_DIRS``).
    Missing files, tables, or keys yield empty lists. Only string list entries
    are honored; malformed values are ignored rather than raising.
    """
    config: DoctorConfig = {"ignore": [], "exclude": []}
    data = _load_pyproject(path)
    if not data:
        return config
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return config
    table = tool.get("azure-functions-doctor")
    if not isinstance(table, dict):
        return config
    for key in ("ignore", "exclude"):
        raw = table.get(key)
        if isinstance(raw, list):
            config[key] = [item for item in raw if isinstance(item, str)]
    return config


def pyproject_declares_dependencies(path: Path) -> bool:
    """Return True when ``pyproject.toml`` declares any runtime or optional
    dependency in the standard ``[project]`` table.
    """
    return bool(pyproject_dependency_names(path))


def is_local_prebuilt_deployment(path: Path, context: Optional["RuleContext"] = None) -> bool:
    """Return True when the project targets a local/prebuilt deployment.

    Azure Functions performs a *remote build* by default, installing
    dependencies from ``requirements.txt`` on the server. A local/prebuilt
    deployment is assumed when the caller explicitly selects a non-remote
    deployment mode (``local``, ``local-prebuilt``, or ``container`` — all of
    which resolve dependencies before/outside the Azure remote build) or when
    dependencies are vendored into a ``.python_packages`` directory (as produced
    by a local/prebuilt build).
    """
    if context is not None and context.get("deployment_mode") in (
        "local",
        "local-prebuilt",
        "container",
    ):
        return True
    return (path / ".python_packages").is_dir()


def _iter_requirements_with_location(req_path: Path) -> list[tuple[Path, int, str]]:
    """Walk ``req_path`` and every local ``-r``/``--requirement`` include it
    reaches, yielding ``(declaring_file, line_no, cleaned_line)`` for each
    actual requirement line.

    Bounded depth and a visited-file guard make this safe against cycles and
    deep include chains. Unlike :func:`_iter_requirements_txt_lines` (which
    flattens every included file's lines into one list), this preserves each
    line's declaring file and original line number, so a consumer can
    attribute a finding to where it is *actually* declared -- the included
    file and line -- rather than to the root file's include directive
    (#587). Remote (``://``) includes and ``-c``/``--constraint`` files are
    not followed, matching this project's existing offline-only scope.
    """
    results: list[tuple[Path, int, str]] = []
    files = dict(iter_requirements_files(req_path))
    seen: set[Path] = set()

    def walk(file_path: Path) -> None:
        if file_path in seen or file_path not in files:
            return
        seen.add(file_path)
        content = files[file_path]
        for line_no, raw_line in enumerate(content.removeprefix("\ufeff").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            directive = parse_include_directive(line)
            if directive is not None:
                include_value = directive.reference
                if "://" not in include_value:
                    include_path = (file_path.parent / include_value).resolve()
                    if not include_path.is_relative_to(req_path.parent.resolve()):
                        continue
                    if directive.constraint:
                        continue
                    walk(include_path)
                continue
            if line.startswith(("-c ", "--constraint")):
                continue
            if line.startswith(("-e ", "--editable")):
                results.append((file_path, line_no, line))
                continue
            if line.startswith("-"):
                continue
            cleaned = line.split("#")[0].strip()
            if cleaned:
                results.append((file_path, line_no, cleaned))

    walk(req_path.resolve())
    return results


def _match_native_dependency_line(line: str, seen: set[str]) -> tuple[str, str] | None:
    """Return ``(package, hint)`` when a single cleaned requirement line
    names a package in ``NATIVE_DEPENDENCY_PACKAGES`` not already in
    ``seen``, handling both the ``-e ...#egg=name`` editable form and an
    ordinary (possibly unparseable) requirement specifier. ``seen`` is
    mutated in place so repeated calls across root + included files never
    double-report the same package (#587).
    """
    if line.startswith(("-e ", "--editable")):
        egg_match = re.search(r"#egg=([^&\s]+)", line)
        if not egg_match:
            return None
        normalized_name = canonicalize_name(egg_match.group(1))
    else:
        normalized_name = None
        try:
            req = Requirement(line)
            normalized_name = canonicalize_name(req.name)
        except InvalidRequirement:
            fallback_name = re.split(r"[=<>!~;\[\]@]", line, maxsplit=1)[0].strip()
            if fallback_name:
                normalized_name = canonicalize_name(fallback_name)

    if normalized_name is None or normalized_name in seen:
        return None
    if normalized_name in NATIVE_DEPENDENCY_PACKAGES:
        seen.add(normalized_name)
        return normalized_name, NATIVE_DEPENDENCY_PACKAGES[normalized_name]
    return None


def _detect_native_dependency_risks(content: str) -> list[tuple[str, str]]:
    """Return matching native-dependency packages in requirements order."""
    matches: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r ", "-c ", "--requirement", "--constraint")):
            continue
        if line.startswith(("-e ", "--editable")):
            match = _match_native_dependency_line(line, seen)
            if match is not None:
                matches.append(match)
            continue
        if line.startswith("-"):
            continue
        line = line.split("#")[0].strip()
        if not line:
            continue
        match = _match_native_dependency_line(line, seen)
        if match is not None:
            matches.append(match)

    return matches


def _detect_native_dependency_risks_for_project(req_path: Path) -> list[tuple[str, str]]:
    """Like :func:`_detect_native_dependency_risks`, but follows local
    ``-r``/``--requirement`` includes from ``req_path`` first (#587), so a
    native-risk package declared only in an included file is still
    detected -- not just one declared directly in the root requirements
    file.
    """
    matches: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _file_path, _line_no, line in _iter_requirements_with_location(req_path):
        match = _match_native_dependency_line(line, seen)
        if match is not None:
            matches.append(match)
    return matches


def _create_result(
    status: str,
    detail: str,
    internal_error: bool = False,
    file: str | None = None,
    line: int | None = None,
    end_line: int | None = None,
    column: int | None = None,
    locations: list[dict[str, object]] | None = None,
) -> HandlerResult:
    """Create a standardized result dictionary (status limited to 'pass'/'fail').

    ``locations`` (issues #394/#395) carries every individual finding as
    ``{"file", "line", "end_line", "column", "message"}`` so SARIF output can
    emit one result per finding instead of collapsing N findings onto the
    first location. When omitted, the scalar ``file``/``line`` fields are the
    single-location form.
    """
    res: HandlerResult = {"status": status, "detail": detail}
    if internal_error:
        res["internal_error"] = "true"
    if file is not None:
        res["file"] = file
    if line is not None:
        res["line"] = line
    if end_line is not None:
        res["end_line"] = end_line
    if column is not None:
        res["column"] = column
    if locations:
        res["locations"] = locations
    return res


def _handle_exception(operation: str, exc: Exception) -> HandlerResult:
    """Handle exceptions consistently across all handlers (always fail)."""
    error_msg = f"Error during {operation}: {type(exc).__name__}"
    logger.error("Diagnostic operation failed: %s (%s)", operation, type(exc).__name__)
    return _create_result("fail", error_msg, internal_error=True)


def _handle_specific_exceptions(operation: str, exc: Exception) -> HandlerResult:
    """Handle specific exception types with user-friendly messages (fail only)."""
    if isinstance(exc, UnicodeDecodeError):
        return _create_result("fail", f"Encoding error in {operation}.", internal_error=True)
    if isinstance(exc, (ValueError, TypeError)):
        return _create_result("fail", f"Configuration error in {operation}.", internal_error=True)
    if isinstance(exc, (OSError, PermissionError)):
        return _create_result("fail", f"File system error in {operation}", internal_error=True)
    if isinstance(exc, ImportError):
        return _create_result("fail", f"Import error in {operation}", internal_error=True)
    if isinstance(exc, MemoryError):
        return _create_result("fail", "Memory error: file too large", internal_error=True)
    if isinstance(exc, KeyboardInterrupt):
        raise exc
    if isinstance(exc, SystemExit):
        raise exc
    logger.error("Unexpected diagnostic error in %s (%s)", operation, type(exc).__name__)
    return _create_result("fail", f"Unexpected error in {operation}", internal_error=True)


class Condition(TypedDict, total=False):
    target: str
    operator: str
    value: str | int | float
    keyword: str
    mode: Literal["string", "ast"]  # for source_code_contains: "string" (default) or "ast"
    jsonpath: str
    targets: list[str]
    patterns: list[str]
    pypi: str
    package: str
    file: str
    decorators: list[str]  # for decorator_order: expected decorator leaf names, outermost-first
    scan_names: list[str]  # for scan_before_spec: endpoint-scan call names
    spec_names: list[str]  # for scan_before_spec: spec-build call names
    flag_missing_auth_level: bool  # for langgraph_anonymous_auth
    blocklist: list[str]  # for durable_nondeterminism: forbidden dotted call names
    decorator_names: list[str]  # for durable_nondeterminism: orchestrator decorator names
    files: list[str]  # for unsupported_metadata_version: metadata file globs
    fields: list[str]  # for unsupported_metadata_version: version field names
    supported_versions: list[str]  # for unsupported_metadata_version: allowed versions


class Rule(TypedDict, total=False):
    id: str
    type: Literal[
        "compare_version",
        "env_var_exists",
        "path_exists",
        "file_exists",
        "package_installed",
        "source_code_contains",
        "conditional_exists",
        "callable_detection",
        "executable_exists",
        "any_of_exists",
        "file_glob_check",
        "host_json_property",
        "host_json_version",
        "local_settings_security",
        "host_json_extension_bundle_version",
        "package_forbidden",
        "package_declared",
        "blueprint_registration",
        "native_dependency_risk",
        "unpinned_requirements",
        "decorator_order",
        "otel_activation",
        "endpoint_metadata",
        "openapi_version_mixing",
        "scan_before_spec",
        "langgraph_anonymous_auth",
        "durable_nondeterminism",
        "unsupported_metadata_version",
        "dev_storage_connection",
        "linux_fx_version",
    ]
    label: str
    category: str
    section: str
    description: str
    required: bool
    severity: Literal["error", "warning", "info"]
    gate: bool
    tier: Literal["core", "extended", "experimental"]
    condition: Condition
    hint: str
    fix: str
    fix_command: str
    hint_url: str
    source_type: Literal["ms_learn", "derived", "heuristic"]
    source_title: str
    source_url: str
    why_it_matters: str
    symptoms: str
    check_order: int


class CompareVersionParams(NamedTuple):
    """Validated parameters for the ``compare_version`` rule type."""

    target: str
    operator: str
    value: str | int | float


class SourceCodeParams(NamedTuple):
    """Validated parameters for the ``source_code_contains`` rule type."""

    keyword: str
    mode: Literal["string", "ast"]


class PackageParams(NamedTuple):
    """Validated parameters for the package declaration rule types."""

    package: str
    file: str


def parse_target(condition: Condition) -> str | None:
    """Return a non-empty ``target`` string from ``condition``, or ``None``."""
    target = condition.get("target")
    return target if isinstance(target, str) and target else None


def parse_compare_version(condition: Condition) -> CompareVersionParams | None:
    """Return validated ``compare_version`` params, or ``None`` if incomplete."""
    target = condition.get("target")
    operator = condition.get("operator")
    value = condition.get("value")
    if (
        isinstance(target, str)
        and target
        and isinstance(operator, str)
        and operator
        and isinstance(value, (str, int, float))
        and not isinstance(value, bool)
    ):
        return CompareVersionParams(target, operator, value)
    return None


def parse_source_code(condition: Condition) -> SourceCodeParams | None:
    """Return validated ``source_code_contains`` params, or ``None``."""
    keyword = condition.get("keyword")
    if not isinstance(keyword, str):
        return None
    if condition.get("mode") == "ast":
        return SourceCodeParams(keyword, "ast")
    return SourceCodeParams(keyword, "string")


def parse_package(condition: Condition) -> PackageParams | None:
    """Return validated package params, falling back from ``package`` to ``target``."""
    package = condition.get("package") or condition.get("target")
    if not isinstance(package, str) or not package:
        return None
    file = condition.get("file", "requirements.txt")
    if not isinstance(file, str) or not file:
        file = "requirements.txt"
    return PackageParams(package, file)


_HOST_JSON_MISSING = object()


def _resolve_host_json_pointer(data: object, parts: list[str]) -> object:
    """Walk a host.json object along dotted ``parts``.

    Returns the resolved node, or ``_HOST_JSON_MISSING`` if any part is absent
    (or an intermediate node is not a dict). An empty ``parts`` list returns
    ``data`` unchanged.
    """
    node: object = data
    for p in parts:
        if isinstance(node, dict) and p in node:
            node = node[p]
        else:
            return _HOST_JSON_MISSING
    return node


def _resolve_host_json_path(data: object, jsonpath: str) -> object:
    """Resolve a ``$.a.b`` style jsonpath against a loaded host.json object.

    Strips a leading ``$.`` (or ``.``) prefix, splits the remainder on ``.``,
    and delegates traversal to :func:`_resolve_host_json_pointer`. Returns the
    resolved node, or ``_HOST_JSON_MISSING`` when the path is absent.
    """
    pointer = jsonpath.lstrip("$.")
    parts = pointer.split(".") if pointer else []
    return _resolve_host_json_pointer(data, parts)


_HandlerFn = TypeVar("_HandlerFn", bound=Callable[..., "HandlerResult"])

# Populated at class-definition time by the @_rule_handler decorator:
# maps a rule type -> the HandlerRegistry method name that handles it.
_RULE_DISPATCH: dict[str, str] = {}


def _rule_handler(func: _HandlerFn) -> _HandlerFn:
    """Register a HandlerRegistry method as the handler for its rule type.

    The rule type is derived from the method name by stripping the
    ``_handle_`` prefix (e.g. ``_handle_compare_version`` -> ``compare_version``).
    """
    _RULE_DISPATCH[func.__name__.removeprefix("_handle_")] = func.__name__
    return func
