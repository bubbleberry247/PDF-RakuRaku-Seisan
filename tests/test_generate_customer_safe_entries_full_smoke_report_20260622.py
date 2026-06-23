from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "generate_customer_safe_entries_full_smoke_report_20260622.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "generate_customer_safe_entries_full_smoke_report_20260622",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def encode_text(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def test_build_scenario_rows_groups_multiple_entries() -> None:
    module = load_module()
    payload = {
        "safety": "customer-safe only",
        "results": [
            {
                "name": "55_v2",
                "exit_code": 0,
                "expected_exit_codes": "0",
                "expected_ok": True,
                "timed_out": False,
                "cleanup_remaining_count": 0,
                "stdout_path": r"C:\run\55.out",
                "stderr_path": r"C:\run\55.err",
                "note": "",
            },
            {
                "name": "70_review",
                "exit_code": 0,
                "expected_exit_codes": "0",
                "expected_ok": True,
                "timed_out": False,
                "cleanup_remaining_count": 0,
                "stdout_path": r"C:\run\70a.out",
                "stderr_path": r"C:\run\70a.err",
                "note": "",
            },
            {
                "name": "70_confirm",
                "exit_code": 3,
                "expected_exit_codes": "0,3",
                "expected_ok": True,
                "timed_out": False,
                "cleanup_remaining_count": 0,
                "stdout_path": r"C:\run\70b.out",
                "stderr_path": r"C:\run\70b.err",
                "note": "承認前提不足は安全BLOCK 3",
            },
        ],
    }

    rows = {row.scenario: row for row in module.build_scenario_rows(payload)}

    assert rows["55"].entry_count == 1
    assert rows["55"].expected_ok_count == 1
    assert rows["70"].entry_count == 2
    assert rows["70"].expected_ok_count == 2
    assert rows["70"].unexpected_count == 0
    assert "70_review, 70_confirm" == rows["70"].entry_names
    assert "SAFE_ENTRY_ONLY_NOT_PRODUCTION_COMPLETE" == rows["70"].production_completion_scope


def test_build_actual_execution_trace_resolves_bat_ps1_and_python_script(tmp_path: Path) -> None:
    module = load_module()
    root_dir = tmp_path / "scenario55"
    root_dir.mkdir()
    script_path = root_dir / "main.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")
    stdout_path = tmp_path / "55_v2.stdout.txt"
    stderr_path = tmp_path / "55_v2.stderr.txt"
    stdout_path.write_text("ok\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    ps1_path = tmp_path / "run_customer_safe_entry.ps1"
    ps1_path.write_text(
        "\n".join(
            [
                f'$root55 = "{encode_text(str(root_dir))}"',
                f'$script55 = "{encode_text(str(script_path))}"',
                '$code = switch ($Entry) {',
                '    "s55_v2" {',
                '        Invoke-PythonStep -CwdB64 $root55 -ScriptB64 $script55 -Args @("--dry-run")',
                "    }",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    bat_path = tmp_path / "55_SAFE_V2_COPY_WRITE_NO_MAIL_ここから起動.bat"
    bat_path.write_text(
        "\n".join(
            [
                "@echo off",
                'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_customer_safe_entry.ps1" -Entry s55_v2',
            ]
        ),
        encoding="utf-8",
    )
    payload = {
        "results": [
            {
                "name": "55_v2",
                "bat_path": str(bat_path),
                "exit_code": 0,
                "expected_exit_codes": "0",
                "expected_ok": True,
                "timed_out": False,
                "elapsed_seconds": 1.25,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        ]
    }

    rows = module.build_actual_execution_trace_rows(payload, ps1_path)

    assert len(rows) == 1
    row = rows[0]
    assert row.scenario == "55"
    assert row.bat_exists == "YES"
    assert row.ps1_exists == "YES"
    assert row.ps1_entry == "s55_v2"
    assert row.ps1_entry_resolved == "YES"
    assert row.command_kind == "PYTHON_SCRIPT"
    assert row.script_paths == str(script_path)
    assert row.script_exists_count == 1
    assert row.script_missing_count == 0
    assert ".bat" in row.file_types
    assert ".ps1" in row.file_types
    assert ".py" in row.file_types
    assert row.stdout_exists == "YES"
    assert row.stderr_exists == "YES"


def test_build_payload_preserves_safe_boundary_and_license_policy() -> None:
    module = load_module()
    payload = module.build_payload(
        {
            "generated_at": "2026-06-23T01:29:06",
            "run_dir": r"C:\run\latest",
            "total": 1,
            "expected_ok_count": 1,
            "unexpected_count": 0,
            "timeout_count": 0,
            "results": [
                {
                    "name": "12_13_scan",
                    "exit_code": 0,
                    "expected_exit_codes": "0",
                    "expected_ok": True,
                    "timed_out": False,
                    "cleanup_remaining_count": 0,
                }
            ],
        }
    )

    assert payload["scenario_count"] == 1
    assert payload["scenario_all_expected_ok_count"] == 1
    assert payload["scenario_unexpected_count"] == 0
    assert "no RK10 ButtonRun" in payload["safety"]
    assert "RPA開発版AI付き" in payload["license_policy"]
    assert payload["actual_trace_entry_count"] == 1
    assert payload["actual_trace_expected_ok_count"] == 1


def test_build_markdown_states_primary_source_and_not_production_complete() -> None:
    module = load_module()
    payload = module.build_payload(
        {
            "generated_at": "2026-06-23T01:29:06",
            "run_dir": r"C:\run\latest",
            "total": 1,
            "expected_ok_count": 1,
            "unexpected_count": 0,
            "timeout_count": 0,
            "results": [
                {
                    "name": "58_gui",
                    "exit_code": 0,
                    "expected_exit_codes": "0",
                    "expected_ok": True,
                    "timed_out": False,
                    "cleanup_remaining_count": 0,
                    "note": "SAFE GUI起動のみ",
                }
            ],
        }
    )

    markdown = module.build_markdown(payload)

    assert "## Primary Source" in markdown
    assert "## Actual Execution Trace" in markdown
    assert "SAFE_ENTRY_ONLY_NOT_PRODUCTION_COMPLETE" in markdown
    assert "SAFE_ENTRY_ACTUAL_BAT_TO_PS1_TO_TOOL_TRACE_NOT_PRODUCTION_COMPLETE" in markdown
    assert "This matrix is safe-entry evidence only" in markdown
    assert "| 58 | 1 | 1 | 0 | 0 | 0 | 58_gui |" in markdown


def test_build_actual_execution_trace_markdown_is_trace_specific() -> None:
    module = load_module()
    payload = module.build_payload(
        {
            "generated_at": "2026-06-23T01:29:06",
            "run_dir": r"C:\run\latest",
            "total": 1,
            "expected_ok_count": 1,
            "unexpected_count": 0,
            "timeout_count": 0,
            "results": [
                {
                    "name": "55_v2",
                    "bat_path": r"C:\safe\55.bat",
                    "exit_code": 0,
                    "expected_exit_codes": "0",
                    "expected_ok": True,
                    "timed_out": False,
                    "cleanup_remaining_count": 0,
                    "stdout_path": r"C:\run\55.stdout.txt",
                    "stderr_path": r"C:\run\55.stderr.txt",
                }
            ],
        }
    )

    matrix_markdown = module.build_markdown(payload)
    trace_markdown = module.build_actual_execution_trace_markdown(payload)

    assert "# 客先安全入口 実行トレース 2026-06-23" in trace_markdown
    assert "# 客先安全入口 シナリオ別証跡マトリクス" not in trace_markdown
    assert "SAFE_ENTRY_ACTUAL_BAT_TO_PS1_TO_TOOL_TRACE_NOT_PRODUCTION_COMPLETE" in trace_markdown
    assert matrix_markdown != trace_markdown
