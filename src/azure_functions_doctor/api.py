from pathlib import Path

from azure_functions_doctor.doctor import Doctor, SectionResult


def run_diagnostics(
    path: str,
    profile: str | None = None,
    rules_path: Path | None = None,
    target_python: str | None = None,
) -> list[SectionResult]:
    """
    Run diagnostics on the Azure Functions application at the specified path.

    Args:
        path: The file system path to the Azure Functions application.
        profile: Optional rule profile ('minimal', 'deploy', 'development', or 'full').

    Returns:
        A list of SectionResult containing the results of each diagnostic check.
    """
    return Doctor(
        path, profile=profile, rules_path=rules_path, target_python=target_python
    ).run_all_checks()
