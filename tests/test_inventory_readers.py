from pathlib import Path

import pytest

from azure_functions_doctor.deploy_config import (
    flex_deployment_storage_shape,
    local_settings_values,
    resolve_target_config,
)
from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.handlers._helpers import (
    _collect_unsupported_metadata_versions,
    _iter_requirements_txt_lines,
    _iter_requirements_with_location,
    _load_pyproject,
    _read_project_python_file,
)
from azure_functions_doctor.handlers.deployment import _infra_declares_linux_fx_version
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.inspection_gaps import collect_inspection_gaps


@pytest.mark.parametrize(
    "kind",
    [
        "functions_extension_version",
        "host_json_property",
        "host_json_version",
        "host_json_extension_bundle_version",
        "conditional_exists",
        "any_of_exists",
        "app_insights_connection",
        "host_json_log_level_conflict",
        "package_declared",
        "package_forbidden",
        "linux_fx_version",
        "dev_storage_connection",
    ],
)
def test_inventory_rule_reader_refuses_large_regular_file(tmp_path: Path, kind: str) -> None:
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\nimport durable_functions\napp=func.FunctionApp()\n"
    )
    rules = Doctor(str(tmp_path)).load_rules()
    rule = next(rule for rule in rules if rule.get("type") == kind)
    if kind == "any_of_exists":
        rule["condition"] = {"targets": ["host.json:version"]}
    elif kind == "host_json_property":
        rule["condition"] = {"jsonpath": "$.version"}
    names = {
        "functions_extension_version": "local.settings.json",
        "package_declared": "requirements.txt",
        "package_forbidden": "requirements.txt",
        "linux_fx_version": "main.bicep",
        "dev_storage_connection": "main.bicep",
    }
    target = tmp_path / names.get(kind, "host.json")
    target.write_text(" " * (4 * 1024 * 1024 + 1) + '{"version":"2.0"}')
    result = HandlerRegistry().handle(rule, tmp_path)
    assert "not inspected" in result["detail"]


@pytest.mark.parametrize("name", ["main.bicep", "azuredeploy.json"])
def test_inventory_flex_infra_helper_refuses_large_file(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_text(" " * (4 * 1024 * 1024) + "linuxFxVersion")
    with collect_inspection_gaps() as gaps:
        assert _infra_declares_linux_fx_version(tmp_path) is False
    assert gaps


@pytest.mark.parametrize("name", ["main.bicep", "azuredeploy.json", "local.settings.json"])
def test_inventory_target_candidates_refuse_large_files(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_text(" " * (4 * 1024 * 1024 + 1))
    with collect_inspection_gaps() as gaps:
        resolve_target_config(tmp_path)
    assert gaps


def test_inventory_flex_storage_reader_refuses_large_json(tmp_path: Path) -> None:
    (tmp_path / "azuredeploy.json").write_text(
        " " * (4 * 1024 * 1024) + '{"deployment":{"storage":{"value":"CANARY"}}}'
    )
    with collect_inspection_gaps() as gaps:
        assert flex_deployment_storage_shape(tmp_path) is None
    assert gaps


def test_inventory_local_values_refuse_large_json(tmp_path: Path) -> None:
    (tmp_path / "local.settings.json").write_text(
        " " * (4 * 1024 * 1024) + '{"Values":{"Secret":"CANARY"}}'
    )
    with collect_inspection_gaps() as gaps:
        assert local_settings_values(tmp_path) == {}
    assert gaps


@pytest.mark.parametrize("candidate", ["host.json", "metadata.json"])
def test_inventory_metadata_reader_refuses_large_json(tmp_path: Path, candidate: str) -> None:
    (tmp_path / candidate).write_text(
        " " * (4 * 1024 * 1024)
        + '{"metadataVersion":"CANARY","extensionBundle":{"version":"CANARY"}}'
    )
    with collect_inspection_gaps() as gaps:
        result = _collect_unsupported_metadata_versions(
            tmp_path, ["metadata.json"], ["metadataVersion"], ["1.0"]
        )
    assert result == []
    assert gaps


def test_inventory_metadata_enumeration_honors_project_excludes(tmp_path: Path) -> None:
    from azure_functions_doctor.handlers._helpers import reset_extra_excludes, set_extra_excludes

    nested = tmp_path / "vendor"
    nested.mkdir()
    (nested / "metadata.json").write_text('{"metadataVersion":"CANARY"}')
    token = set_extra_excludes(tmp_path, ["vendor"])
    try:
        result = _collect_unsupported_metadata_versions(
            tmp_path, ["metadata.json"], ["metadataVersion"], ["1.0"]
        )
    finally:
        reset_extra_excludes(token)
    assert result == []


def test_inventory_toml_reader_refuses_large_file(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("#" + "x" * (4 * 1024 * 1024))
    with collect_inspection_gaps() as gaps:
        assert _load_pyproject(tmp_path) is None
    assert gaps


def test_inventory_decode_fallback_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_bytes(b"\xffapp=func.FunctionApp()")
    with collect_inspection_gaps() as gaps:
        assert _read_project_python_file(source) is None
    assert gaps


@pytest.mark.parametrize("walker", ["flattened", "located"])
@pytest.mark.parametrize("hostile", ["large", "files", "bytes", "depth", "alias"])
def test_inventory_include_walkers_have_visible_bounds(
    tmp_path: Path, walker: str, hostile: str
) -> None:
    root = tmp_path / "requirements.txt"
    content = "-r include.txt\n"
    if hostile == "large":
        (tmp_path / "include.txt").write_text("#" + "x" * (4 * 1024 * 1024))
    elif hostile == "alias":
        (tmp_path / "real.txt").write_text("numpy\n")
        (tmp_path / "include.txt").symlink_to(tmp_path / "real.txt")
    elif hostile == "files":
        content = "".join(f"-r r{i}.txt\n" for i in range(130))
        for i in range(130):
            (tmp_path / f"r{i}.txt").write_text("numpy\n")
    elif hostile == "bytes":
        content = "".join(f"-r r{i}.txt\n" for i in range(6))
        for i in range(6):
            (tmp_path / f"r{i}.txt").write_text("#" + "x" * (3 * 1024 * 1024))
    else:
        content = "-r r0.txt\n"
        for i in range(12):
            (tmp_path / f"r{i}.txt").write_text(f"-r r{i + 1}.txt\n")
    root.write_text(content)
    with collect_inspection_gaps() as gaps:
        if walker == "flattened":
            _iter_requirements_txt_lines(content, root)
        else:
            _iter_requirements_with_location(root)
    assert gaps


@pytest.mark.parametrize("walker", ["flattened", "located"])
def test_inventory_include_cycles_remain_safe(tmp_path: Path, walker: str) -> None:
    root = tmp_path / "requirements.txt"
    content = "azure-functions\n-r child.txt\n"
    root.write_text(content)
    (tmp_path / "child.txt").write_text("requests\n-r requirements.txt\n")
    if walker == "flattened":
        result = _iter_requirements_txt_lines(content, root)
        assert result == ["azure-functions", "requests"]
    else:
        located = _iter_requirements_with_location(root)
        assert [line for _, _, line in located] == ["azure-functions", "requests"]


@pytest.mark.parametrize("kind", ["package_declared", "package_forbidden"])
@pytest.mark.parametrize("reference", ["absolute", "../outside.txt"])
def test_inventory_configured_manifest_is_root_contained(
    tmp_path: Path, kind: str, reference: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("azure-functions\n")
    rule = next(rule for rule in Doctor(str(project)).load_rules() if rule.get("type") == kind)
    rule["condition"] = {
        "package": "azure-functions",
        "file": str(outside) if reference == "absolute" else reference,
    }
    result = HandlerRegistry().handle(rule, project)
    assert "not inspected" in result["detail"]


def test_inventory_metadata_symlink_cannot_ingest_outside(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"metadataVersion":"CANARY_OUTSIDE"}')
    (project / "metadata.json").symlink_to(outside)
    result = _collect_unsupported_metadata_versions(
        project, ["metadata.json"], ["metadataVersion"], ["1.0"]
    )
    assert result == []
