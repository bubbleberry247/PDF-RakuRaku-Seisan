from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "run_customer_safe_entries_full_smoke_20260622.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "run_customer_safe_entries_full_smoke_20260622",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_safe_entries_cover_all_customer_bats() -> None:
    module = load_module()

    assert len(module.SAFE_ENTRIES) == 22
    assert {entry.name for entry in module.SAFE_ENTRIES} >= {
        "12_13_scan",
        "55_v2",
        "58_gui",
        "70_confirm",
        "71_pytest",
    }


def test_expected_safe_stop_exit_codes_are_explicit() -> None:
    module = load_module()
    entries = {entry.name: entry for entry in module.SAFE_ENTRIES}

    assert entries["38_precheck"].expected_exit_codes == (0, 1)
    assert entries["55_v2"].timeout_seconds >= 900
    assert entries["56_prod"].expected_exit_codes == (0, 1)
    assert entries["70_confirm"].expected_exit_codes == (0, 3)
    assert entries["58_gui"].cleanup_marker == module.S58_PROCESS_MARKER


def test_cleanup_does_not_match_its_own_powershell_process() -> None:
    module = load_module()

    source = inspect.getsource(module.cleanup_processes)

    assert "$_.ProcessId -ne $PID" in source


def test_build_payload_counts_expected_and_timeout() -> None:
    module = load_module()
    payload = module.build_payload(
        [
            module.EntryResult(
                name="ok",
                bat_path="ok.bat",
                exit_code=0,
                expected_exit_codes="0",
                expected_ok=True,
                timed_out=False,
                elapsed_seconds=1.0,
                stdout_path="ok.out",
                stderr_path="ok.err",
                stdout_bytes=1,
                stderr_bytes=0,
                note="",
                cleanup_found_count=0,
                cleanup_remaining_count=0,
                cleanup_json_path="",
            ),
            module.EntryResult(
                name="timeout",
                bat_path="timeout.bat",
                exit_code=None,
                expected_exit_codes="0",
                expected_ok=False,
                timed_out=True,
                elapsed_seconds=2.0,
                stdout_path="timeout.out",
                stderr_path="timeout.err",
                stdout_bytes=0,
                stderr_bytes=0,
                note="",
                cleanup_found_count=0,
                cleanup_remaining_count=0,
                cleanup_json_path="",
            ),
        ],
        Path(r"C:\tmp\run"),
    )

    assert payload["expected_ok_count"] == 1
    assert payload["unexpected_count"] == 1
    assert payload["timeout_count"] == 1


def test_markdown_states_no_production_side_effects() -> None:
    module = load_module()
    payload = module.build_payload([], Path(r"C:\tmp\run"))

    markdown = module.build_markdown(payload)

    assert "実メールなし" in markdown
    assert "RK10 ButtonRun" in markdown
    assert "RPA開発版AI付き" in markdown
