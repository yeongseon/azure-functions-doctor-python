"""Canaries exercise the real diagnostic surfaces, not a redaction mock."""

from dataclasses import asdict
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.agent import load_agent_report
from azure_functions_doctor.api import run_diagnostics
from azure_functions_doctor.cli import cli
from azure_functions_doctor.handlers._helpers import _handle_specific_exceptions
from azure_functions_doctor.handlers.registry import HandlerRegistry

SECRET = "CANARY_SECRET_DIAGNOSTIC"
CANARIES = (
    SECRET,
    f"DefaultEndpointsProtocol=https;AccountName=fake;AccountKey={SECRET}",
    f"Endpoint=sb://fake.invalid/;SharedAccessKeyName=test;SharedAccessKey={SECRET}",
    f"InstrumentationKey={SECRET}",
    f"https://fake.invalid/package.zip?sv=1&sig={SECRET}",
    f"Bearer eyJhbGciOiJIUzI1NiJ9.{SECRET}.signature",
    f"https://fake.invalid/api?code={SECRET}",
    f"x-functions-key: {SECRET}",
)


def project(root: Path, secret: str = SECRET) -> None:
    root.joinpath("function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n"
        "@app.queue_trigger(arg_name='m', queue_name='q', connection='MissingConnection')\n"
        "def consume(m): pass\n"
        f"# {secret}\n",
        encoding="utf-8",
    )
    root.joinpath("requirements.txt").write_text("azure-functions\n", encoding="utf-8")
    root.joinpath("host.json").write_text(
        json.dumps({"version": "2.0", "instrumentationKey": secret}), encoding="utf-8"
    )
    root.joinpath("local.settings.json").write_text(
        json.dumps(
            {
                "Values": {
                    "FUNCTIONS_EXTENSION_VERSION": secret,
                    "UnknownApplicationSetting": secret,
                    "StorageConnection": secret,
                    "APPLICATIONINSIGHTS_CONNECTION_STRING": secret,
                }
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize("secret", CANARIES)
@pytest.mark.parametrize("format_type", ["table", "json", "sarif", "junit"])
def test_default_outputs_mask_values_when_settings_contain_secrets(
    tmp_path: Path, secret: str, format_type: str
) -> None:
    # Given real settings and source containing credentials, including an invalid runtime pin.
    project(tmp_path, secret)
    output = tmp_path / "report.txt"
    summary = tmp_path / "counts.json"
    # When the CLI writes the requested artifact and Action summary sidecar.
    result = CliRunner().invoke(
        cli,
        [
            "doctor",
            "--path",
            str(tmp_path),
            "--format",
            format_type,
            "--output",
            str(output),
            "--summary-json",
            str(summary),
            "--verbose",
        ],
    )
    # Then findings remain useful without persisting credentials.
    assert result.exception is None or isinstance(result.exception, SystemExit)
    artifact = output.read_text(encoding="utf-8")
    assert SECRET not in artifact + result.output + summary.read_text(encoding="utf-8")
    assert "FUNCTIONS_EXTENSION_VERSION" in artifact
    assert "MissingConnection" in artifact
    if format_type == "json":
        report = json.loads(artifact)
        assert report["schema_version"] == "2.0"
        findings = [item for section in report["results"] for item in section["items"]]
        finding = next(f for f in findings if f["rule_id"] == "check_functions_extension_version")
        assert finding["status"] == "warn"
        assert finding["hint"]
        assert SECRET not in json.dumps(asdict(load_agent_report(output)))


def test_api_masks_values_when_settings_contain_secrets(tmp_path: Path) -> None:
    # Given the same project used by the CLI.
    project(tmp_path)
    # When called through the public API.
    results = run_diagnostics(str(tmp_path))
    # Then the shared finding contract is safe before serialization.
    assert SECRET not in json.dumps(results)
    assert any(
        i["rule_id"] == "check_functions_extension_version" for s in results for i in s["items"]
    )


@pytest.mark.parametrize("error", [ValueError, TypeError, OSError, ImportError, RuntimeError])
def test_exception_details_omit_payload_when_nested_error_contains_secret(
    error: type[Exception], caplog: pytest.LogCaptureFixture
) -> None:
    # Given an exception whose message and chained cause contain credentials.
    try:
        try:
            raise ValueError(SECRET)
        except ValueError as cause:
            raise error(f"Authorization: Bearer {SECRET}") from cause
    except Exception as exc:
        # When the diagnostic boundary handles it.
        result = _handle_specific_exceptions("reading local.settings.json", exc)
    # Then neither finding nor traceback logging reveals either payload.
    assert result["status"] == "fail"
    assert result["internal_error"] == "true"
    assert "local.settings.json" in result["detail"]
    assert SECRET not in repr(result) + caplog.text


@pytest.mark.parametrize(
    "host",
    [
        {"version": SECRET},
        {"version": "2.0", "extensionBundle": {"id": SECRET, "version": "[4.*, 5.0.0)"}},
        {
            "version": "2.0",
            "extensionBundle": {
                "id": "Microsoft.Azure.Functions.ExtensionBundle",
                "version": SECRET,
            },
        },
        {"version": "2.0", "logging": {"logLevel": {"default": SECRET}}},
    ],
)
def test_host_values_are_masked_when_invalid(tmp_path: Path, host: dict[str, object]) -> None:
    # Given a credential accidentally placed in a host configuration field.
    project(tmp_path, "~4")
    (tmp_path / "host.json").write_text(json.dumps(host), encoding="utf-8")
    # When all real rules run; Then diagnostic values do not echo unknown host values.
    results = run_diagnostics(str(tmp_path))
    assert SECRET not in json.dumps(results)


def test_flex_runtime_and_auth_fields_mask_unknown_values(tmp_path: Path) -> None:
    # Given credentials in fields ingested by the deployment configuration resolver.
    project(tmp_path, "~4")
    (tmp_path / "infra.json").write_text(
        json.dumps(
            {
                "functionAppConfig": {
                    "runtime": {"name": "python", "version": SECRET},
                    "deployment": {
                        "storage": {
                            "value": "https://fake.invalid/?sig=" + SECRET,
                            "authentication": {"type": SECRET},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    # When deployment diagnostics run; Then findings retain field names, not credentials.
    results = run_diagnostics(str(tmp_path))
    assert SECRET not in json.dumps(results)
    assert "functionAppConfig.runtime" in json.dumps(results)


def test_malformed_json_error_omits_echoed_content(tmp_path: Path) -> None:
    # Given an invalid escape sequence whose decoder error contains source characters.
    (tmp_path / "host.json").write_text('{"version":"\\uCANARY_SECRET_BAD"}', encoding="utf-8")
    # When the host rule handles the decoder failure; Then payload remains private.
    result = HandlerRegistry().handle({"type": "host_json_version"}, tmp_path)
    assert "CANARY_SECRET" not in repr(result)
    assert result["status"] == "fail"
