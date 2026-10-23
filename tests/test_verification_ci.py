from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_workflows_reuse_runners_and_keep_failure_evidence() -> None:
    workflows = ROOT / ".github/workflows"
    ci = (workflows / "ci-test.yml").read_text()
    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in ci
    assert "python -m tools.verification test --no-cov" in ci
    assert "python -m tools.verification host-smoke" in ci
    assert "make install-ci" in ci
    for name in ("ci-test.yml", "e2e-azure.yml", "publish-pypi.yml"):
        text = (workflows / name).read_text()
        evidence = [
            block for block in text.split("      - name:") if "path: test-results/**" in block
        ]
        assert evidence
        assert all("if: always()" in block for block in evidence)


def test_existing_ci_job_names_and_release_needs_remain_unchanged() -> None:
    ci = (ROOT / ".github/workflows/ci-test.yml").read_text()
    assert re.findall(r"^    name: (.+)$", ci, re.MULTILINE) == [
        "Lint and type-check (Py 3.11)",
        "Test (Py ${{ matrix.python-version }})",
        "Documentation checks (Py 3.11)",
        "Minimum dependencies (Py 3.11)",
        "Build compatibility artifacts",
        "Wheel install rejection (Py 3.10, negative test)",
        "Wheel install and CLI smoke (Py 3.11)",
        "Real Functions host smoke (Py ${{ matrix.python-version }})",
    ]
    release = (ROOT / ".github/workflows/publish-pypi.yml").read_text()
    assert "needs: [build, lib-tests, doctor-runtime-gate, azure-e2e]" in release
