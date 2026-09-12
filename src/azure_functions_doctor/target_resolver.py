from pathlib import Path
import re
import shutil
import subprocess  # nosec B404
import sys
from typing import Callable, Dict, Optional, Tuple

from azure_functions_doctor.compatibility import load_catalog
from azure_functions_doctor.logging_config import get_logger

logger = get_logger(__name__)

# Python versions supported by Azure Functions and the per-plan support matrix are
# derived from the version-controlled compatibility catalog
# (assets/compatibility/catalog.json), the single auditable source of truth for
# every date/compatibility fact. The names below are preserved for backward
# compatibility with existing handler and CLI imports.
#
# Python support is not uniform across hosting plans: Linux Consumption is capped
# at Python 3.12 ("the last Python version supported for Linux Consumption plan
# apps"), while Flex Consumption, Premium (Elastic Premium), and Dedicated (App
# Service) plans track the newer runtimes. A flat allow-list would pass invalid
# combinations such as Python 3.14 on Linux Consumption, so support is modelled as
# a per-plan matrix.
_CATALOG = load_catalog()
SUPPORTED_PYTHON_VERSIONS: Tuple[str, ...] = _CATALOG.supported_python_versions()
PYTHON_HOSTING_PLAN_MATRIX: Dict[str, Tuple[str, ...]] = dict(_CATALOG.hosting_plan_matrix())

# Hosting plans recognized by the Python-version compatibility matrix.
SUPPORTED_HOSTING_PLANS: Tuple[str, ...] = tuple(PYTHON_HOSTING_PLAN_MATRIX)


def _major_minor(version: str) -> Optional[Tuple[int, int]]:
    """Return the ``(major, minor)`` pair for a version string, or ``None``."""
    match = _PYTHON_VERSION_RE.search(version)
    if not match:
        return None
    parts = match.group(1).split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return None


def is_supported_python_target(version: str) -> bool:
    """Return ``True`` when ``version``'s major.minor is a supported Azure target.

    Only the major and minor components are considered, so patch releases such
    as ``"3.14.2"`` are supported while ``"3.15.0"`` and ``"3.9.1"`` are not.
    """
    parsed = _major_minor(version)
    if parsed is None:
        return False
    supported = {_major_minor(v) for v in SUPPORTED_PYTHON_VERSIONS}
    return parsed in supported


def is_supported_python_for_plan(version: str, plan: str) -> bool:
    """Return ``True`` when ``version`` is supported on the given hosting ``plan``.

    Only the major.minor components are considered. Unknown plans fall back to
    the plan-agnostic :func:`is_supported_python_target` check so callers never
    reject a version merely because the plan name is unrecognized.
    """
    allowed = PYTHON_HOSTING_PLAN_MATRIX.get(plan)
    if allowed is None:
        return is_supported_python_target(version)
    parsed = _major_minor(version)
    if parsed is None:
        return False
    supported = {_major_minor(v) for v in allowed}
    return parsed in supported


def _resolve_python(override: Optional[str] = None) -> str:
    """Resolve the running Python interpreter version."""
    return override if override is not None else sys.version.split()[0]


_PYTHON_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


def resolve_python_target(
    project_path: Optional[Path] = None, override: Optional[str] = None
) -> Tuple[str, str]:
    """Resolve the Python version to diagnose against, with provenance.

    Precedence (first match wins):

    1. Explicit ``override`` (e.g. ``--target-python``) -> source ``"override"``.
    2. ``.python-version`` file -> source ``".python-version"``.
    3. The running interpreter -> source ``"tool-runtime"`` (always resolves).

    The ``[project] requires-python`` value in ``pyproject.toml`` is deliberately
    NOT used as the target: it declares a compatibility *floor*, not the
    interpreter the app will actually be deployed against, so treating it as the
    target masks unsupported runtimes.

    Args:
        project_path: Root of the project under diagnosis. When ``None`` or when
            no project signal is found, the running interpreter is used.
        override: Explicit target that short-circuits project detection.

    Returns:
        A ``(version, source)`` tuple where ``source`` records provenance.
    """
    if override is not None:
        return override, "override"

    if project_path is not None:
        python_version_file = project_path / ".python-version"
        if python_version_file.is_file():
            try:
                content = python_version_file.read_text(encoding="utf-8").strip()
            except OSError:
                content = ""
            match = _PYTHON_VERSION_RE.search(content)
            if match:
                return match.group(1), ".python-version"

    return sys.version.split()[0], "tool-runtime"


def _resolve_func_core_tools(override: Optional[str] = None) -> str:
    """Resolve the installed Azure Functions Core Tools version."""
    func_path = shutil.which("func")
    if not func_path:
        logger.debug("Azure Functions Core Tools not found in PATH")
        return "not_installed"
    try:
        output = subprocess.check_output([func_path, "--version"], text=True, timeout=10)  # nosec B603
        return output.strip()
    except FileNotFoundError:
        logger.debug("Azure Functions Core Tools executable disappeared before execution")
        return "not_installed"
    except subprocess.TimeoutExpired:
        logger.warning("Timeout getting func version")
        return "timeout"
    except TimeoutError:
        logger.warning("Timeout getting func version")
        return "timeout"
    except subprocess.CalledProcessError as e:
        logger.warning(f"func command failed with code {e.returncode}")
        return f"error_{e.returncode}"
    except Exception as exc:
        logger.error(f"Unexpected error getting func version: {exc}")
        return "unknown_error"


# Registry mapping a target name to its resolver callable.
_TARGET_RESOLVERS: Dict[str, Callable[[Optional[str]], str]] = {
    "python": _resolve_python,
    "func_core_tools": _resolve_func_core_tools,
}


def resolve_target_value(target: str, override: Optional[str] = None) -> str:
    """
    Resolve the current value of a target used in version comparison or diagnostics.

    Args:
        target: The name of the target to resolve. Examples include "python" or "func_core_tools".

    Returns:
        A string representing the resolved version or value.

    Raises:
        ValueError: If the target is not recognized.
    """
    resolver = _TARGET_RESOLVERS.get(target)
    if resolver is None:
        raise ValueError(f"Unknown target: {target}")
    return resolver(override)
