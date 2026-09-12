import ast
import contextvars
from fnmatch import fnmatch
import json
from pathlib import Path
import re
import sys
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Literal,
    NamedTuple,
    Optional,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

try:  # Python 3.11+ ships tomllib in the stdlib
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

from azure_functions_doctor.logging_config import get_logger

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
_extra_excludes: contextvars.ContextVar[Tuple[Path, Tuple[str, ...]]] = contextvars.ContextVar(
    "_extra_excludes", default=(Path(), ())
)


def set_extra_excludes(
    root: Path, globs: Iterable[str]
) -> contextvars.Token[Tuple[Path, Tuple[str, ...]]]:
    """Set the active extra-exclude globs and return a reset token."""
    normalized = tuple(g for g in globs if g)
    return _extra_excludes.set((root, normalized))


def reset_extra_excludes(
    token: contextvars.Token[Tuple[Path, Tuple[str, ...]]],
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
    if any(part in EXCLUDED_PROJECT_DIRS for part in candidate.parts):
        return True
    return _matches_extra_exclude(candidate)


def iter_project_files(
    project_path: Path, patterns: Union[str, tuple[str, ...], list[str]]
) -> Iterator[Path]:
    """Single entry point for project file traversal (issue #393).

    Yields files under ``project_path`` matching ``patterns`` (rglob syntax),
    honoring ``EXCLUDED_PROJECT_DIRS`` and the user's
    ``[tool.azure-functions-doctor].exclude`` globs. Handlers must traverse
    through this helper instead of calling ``Path.rglob`` directly so
    virtualenvs, node_modules, caches, and user excludes are never scanned -
    a regression test forbids raw rglob outside this module.
    """
    pattern_list: tuple[str, ...]
    if isinstance(patterns, str):
        pattern_list = (patterns,)
    else:
        pattern_list = tuple(patterns)
    for pattern in pattern_list:
        for candidate in sorted(project_path.rglob(pattern)):
            if not _is_excluded_path(candidate):
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
    locations: List[Dict[str, object]]
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
    target_python: Optional[str]
    deployment_mode: Optional[str]
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


def _discover_functionapp_aliases(source: str) -> set[str]:
    """Extract variable names assigned a ``FunctionApp()`` or ``Blueprint()`` call.

    Scans AST assignments like ``app = func.FunctionApp()`` and
    ``bp = Blueprint()`` to discover alias names used for decorators.
    Returns the set of discovered names, or ``{"app"}`` when none are found.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"app"}

    names: set[str] = set()
    target_attrs = {"FunctionApp", "Blueprint"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func_node = node.value.func
            attr_name: str | None = None
            if isinstance(func_node, ast.Attribute):
                attr_name = func_node.attr
            elif isinstance(func_node, ast.Name):
                attr_name = func_node.id
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

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func_node = node.value.func
            attr_name: str | None = None
            if isinstance(func_node, ast.Attribute):
                attr_name = func_node.attr
            elif isinstance(func_node, ast.Name):
                attr_name = func_node.id
            if attr_name != "Blueprint":
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _collect_register_functions_args(source: str) -> set[str]:
    """Collect Blueprint aliases passed to ``register_functions(...)`` calls.

    Only the official Azure Functions Python v2 API (``app.register_functions``)
    is recognized. Flask/FastAPI-style ``register_blueprint`` is intentionally
    not accepted because it is not a valid registration call for the Azure
    Functions runtime.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func_node = node.func
        if not isinstance(func_node, ast.Attribute):
            continue
        if func_node.attr != "register_functions":
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
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.decorator_list:
            for dec in node.decorator_list:
                alias = decorator_alias(dec)
                if alias is not None:
                    matched_aliases.add(alias)
    return matched_aliases


def _collect_unregistered_blueprint_aliases(path: Path) -> set[str]:
    """Collect Blueprint aliases that are decorated but never registered."""
    project_contents = list(_iter_project_py_contents(path))
    blueprint_aliases: set[str] = set()

    for _py_file, content in project_contents:
        blueprint_aliases |= _collect_blueprint_aliases(content)

    decorated_blueprint_aliases: set[str] = set()
    registered_blueprint_aliases: set[str] = set()

    for _py_file, content in project_contents:
        decorated_blueprint_aliases |= _source_contains_blueprint_decorator(
            content, blueprint_aliases
        )
        registered_blueprint_aliases |= _collect_register_functions_args(content)

    return decorated_blueprint_aliases - registered_blueprint_aliases


def _decorator_simple_name(dec: ast.expr) -> Optional[str]:
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
    validate_idx: Optional[int] = None
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
    return canonicalize_name("azure-functions-openapi") in _parse_requirements_names(content)


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
    return canonicalize_name("azure-functions-validation") in _parse_requirements_names(content)


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
) -> list[tuple[str, int, Optional[int], int]]:
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
    uncovered: list[tuple[str, int, Optional[int], int]] = []
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
            route_idx: Optional[int] = None
            validate_idx: Optional[int] = None
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


def _dotted_call_name(func: ast.expr) -> Optional[str]:
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


def _project_declares_opentelemetry(path: Path) -> bool:
    """Return True when the project declares any ``opentelemetry`` distribution in
    ``requirements.txt`` or ``pyproject.toml`` (runtime or optional dependencies).

    The ``azure-functions-logging[otel]`` extra pulls in ``opentelemetry-api``, so
    any declared ``opentelemetry-*`` package satisfies the activation requirement.
    """
    declared: set[str] = set(pyproject_dependency_names(path))
    req_path = path / "requirements.txt"
    if req_path.exists():
        content = _read_project_python_file(req_path)
        if content is not None:
            declared |= _parse_requirements_names(content)
    return any(name.startswith("opentelemetry") for name in declared)


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
            return json.loads(p.read_text(encoding="utf-8"))
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
        for match in path.rglob(pattern):
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
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.decorator_list:
            for dec in node.decorator_list:
                if decorator_matches(dec):
                    return True
    return False


def _iter_project_py_contents(path: Path) -> Iterator[tuple[Path, str]]:
    """Yield (py_file, content) for each .py file under path, skipping excluded dirs."""
    for py_file in iter_project_files(path, "*.py"):
        content = _read_project_python_file(py_file)
        if content is None:
            continue
        yield py_file, content


def _read_project_python_file(py_file: Path) -> Optional[str]:
    """Read Python source without failing the whole traversal."""
    try:
        return py_file.read_text(encoding="utf-8")
    except PermissionError:
        logger.warning(f"Permission denied reading {py_file}")
        return None
    except UnicodeDecodeError:
        try:
            return py_file.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError, ValueError) as exc:
            logger.debug(f"Skip {py_file}: {exc}")
            return None
    except (MemoryError, OSError, ValueError) as exc:
        logger.debug(f"Skip {py_file}: {exc}")
        return None


def _parse_requirements_names(content: str) -> set[str]:
    """Extract normalized package names from requirements.txt content.

    Handles extras (``requests[security]``), environment markers (``;``),
    URL installs (``@``), pip directives (``-r``, ``-e``), and inline comments.
    """
    names: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Skip -r / -c / --requirement / --constraint includes
        if line.startswith(("-r ", "-c ", "--requirement", "--constraint")):
            continue
        # Handle editable installs: -e git+...#egg=name
        if line.startswith(("-e ", "--editable")):
            egg_match = re.search(r"#egg=([^&\s]+)", line)
            if egg_match:
                names.add(canonicalize_name(egg_match.group(1)))
            continue
        # Skip other pip flags (--find-links, --index-url, etc.)
        if line.startswith("-"):
            continue
        # Strip inline comments
        line = line.split("#")[0].strip()
        if not line:
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


def _load_pyproject(path: Path) -> Optional[Dict[str, object]]:
    """Load and parse ``pyproject.toml`` from ``path``.

    Returns the parsed table, or ``None`` when the file is absent, unreadable,
    or not valid TOML.
    """
    pyproject_path = path / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    try:
        with pyproject_path.open("rb") as handle:
            data: Dict[str, object] = tomllib.load(handle)
            return data
    except (OSError, ValueError) as exc:
        logger.debug(f"Skip pyproject.toml at {pyproject_path}: {exc}")
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

    ignore: List[str]
    exclude: List[str]


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
            egg_match = re.search(r"#egg=([^&\s]+)", line)
            if egg_match:
                normalized_egg = canonicalize_name(egg_match.group(1))
                if normalized_egg in NATIVE_DEPENDENCY_PACKAGES and normalized_egg not in seen:
                    matches.append((normalized_egg, NATIVE_DEPENDENCY_PACKAGES[normalized_egg]))
                    seen.add(normalized_egg)
            continue
        if line.startswith("-"):
            continue
        line = line.split("#")[0].strip()
        if not line:
            continue

        normalized_name: str | None = None
        try:
            req = Requirement(line)
            normalized_name = canonicalize_name(req.name)
        except InvalidRequirement:
            fallback_name = re.split(r"[=<>!~;\[\]@]", line, maxsplit=1)[0].strip()
            if fallback_name:
                normalized_name = canonicalize_name(fallback_name)

        if normalized_name is None or normalized_name in seen:
            continue
        if normalized_name in NATIVE_DEPENDENCY_PACKAGES:
            matches.append((normalized_name, NATIVE_DEPENDENCY_PACKAGES[normalized_name]))
            seen.add(normalized_name)

    return matches


def _create_result(
    status: str,
    detail: str,
    internal_error: bool = False,
    file: Optional[str] = None,
    line: Optional[int] = None,
    end_line: Optional[int] = None,
    column: Optional[int] = None,
    locations: Optional[List[Dict[str, object]]] = None,
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
    error_msg = f"Error during {operation}: {exc}"
    logger.error(error_msg, exc_info=True)
    return _create_result("fail", error_msg, internal_error=True)


def _handle_specific_exceptions(operation: str, exc: Exception) -> HandlerResult:
    """Handle specific exception types with user-friendly messages (fail only)."""
    if isinstance(exc, UnicodeDecodeError):
        return _create_result("fail", f"Encoding error in {operation}: {exc}.", internal_error=True)
    if isinstance(exc, (ValueError, TypeError)):
        return _create_result(
            "fail", f"Configuration error in {operation}: {exc}.", internal_error=True
        )
    if isinstance(exc, (OSError, PermissionError)):
        return _create_result(
            "fail", f"File system error in {operation}: {exc}", internal_error=True
        )
    if isinstance(exc, ImportError):
        return _create_result("fail", f"Import error in {operation}: {exc}", internal_error=True)
    if isinstance(exc, MemoryError):
        return _create_result("fail", "Memory error: file too large", internal_error=True)
    if isinstance(exc, KeyboardInterrupt):
        raise exc
    if isinstance(exc, SystemExit):
        raise exc
    logger.error(f"Unexpected error in {operation}: {exc}", exc_info=True)
    return _create_result("fail", f"Unexpected error in {operation}", internal_error=True)


class Condition(TypedDict, total=False):
    target: str
    operator: str
    value: Union[str, int, float]
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
        "decorator_order",
        "endpoint_metadata",
        "openapi_version_mixing",
        "scan_before_spec",
        "langgraph_anonymous_auth",
        "durable_nondeterminism",
        "unsupported_metadata_version",
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
    value: Union[str, int, float]


class SourceCodeParams(NamedTuple):
    """Validated parameters for the ``source_code_contains`` rule type."""

    keyword: str
    mode: Literal["string", "ast"]


class PackageParams(NamedTuple):
    """Validated parameters for the package declaration rule types."""

    package: str
    file: str


def parse_target(condition: Condition) -> Optional[str]:
    """Return a non-empty ``target`` string from ``condition``, or ``None``."""
    target = condition.get("target")
    return target if isinstance(target, str) and target else None


def parse_compare_version(condition: Condition) -> Optional[CompareVersionParams]:
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


def parse_source_code(condition: Condition) -> Optional[SourceCodeParams]:
    """Return validated ``source_code_contains`` params, or ``None``."""
    keyword = condition.get("keyword")
    if not isinstance(keyword, str):
        return None
    if condition.get("mode") == "ast":
        return SourceCodeParams(keyword, "ast")
    return SourceCodeParams(keyword, "string")


def parse_package(condition: Condition) -> Optional[PackageParams]:
    """Return validated package params, falling back from ``package`` to ``target``."""
    package = condition.get("package") or condition.get("target")
    if not isinstance(package, str) or not package:
        return None
    file = condition.get("file", "requirements.txt")
    if not isinstance(file, str) or not file:
        file = "requirements.txt"
    return PackageParams(package, file)


_HOST_JSON_MISSING = object()


def _resolve_host_json_pointer(data: object, parts: List[str]) -> object:
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
_RULE_DISPATCH: Dict[str, str] = {}


def _rule_handler(func: _HandlerFn) -> _HandlerFn:
    """Register a HandlerRegistry method as the handler for its rule type.

    The rule type is derived from the method name by stripping the
    ``_handle_`` prefix (e.g. ``_handle_compare_version`` -> ``compare_version``).
    """
    _RULE_DISPATCH[func.__name__.removeprefix("_handle_")] = func.__name__
    return func
