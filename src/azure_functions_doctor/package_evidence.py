from pathlib import Path

from azure_functions_doctor.handlers._helpers import (
    _iter_project_py_contents,
    _parse_requirements_names,
    _read_project_python_file,
)


def declares_package(path: Path, distribution: str) -> bool:
    requirements = path / "requirements.txt"
    if requirements.is_file():
        content = _read_project_python_file(requirements)
        if content is not None and distribution in _parse_requirements_names(content, requirements):
            return True
    import ast

    module = distribution.replace("-", "_")
    for _, source in _iter_project_py_contents(path):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == module or node.module.startswith(module + "."):
                    return True
            if isinstance(node, ast.Import):
                if any(
                    alias.name == module or alias.name.startswith(module + ".")
                    for alias in node.names
                ):
                    return True
    return False
