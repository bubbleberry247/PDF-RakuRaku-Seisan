import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "validate_rks_runtime_operator_intake_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("validate_rks_runtime_operator_intake_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_pack(path: Path) -> None:
    payload = {
        "rows": [
            {
                "scenario": "37",
                "rks_path": r"C:\RK10\37.rks",
                "status": "WAITING_OPERATOR_RK10_EVIDENCE",
                "requires_rk10_evidence": True,
            },
            {
                "scenario": "12/13",
                "rks_path": "",
                "status": "NO_PRIMARY_RKS",
                "requires_rk10_evidence": False,
            },
            {
                "scenario": "44",
                "rks_path": r"C:\RK10\44.rks",
                "status": "WAITING_PREREQUISITE_BEFORE_RKS_RUNTIME",
                "requires_rk10_evidence": False,
            },
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_intake(path: Path, rows: list[dict[str, str]]) -> None:
    module = load_module()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.REQUIRED_COLUMNS if hasattr(module, "REQUIRED_COLUMNS") else [
            "scenario",
            "rks_path",
            "operator_decision",
            "rk10_editor_open",
            "rk10_build",
            "runtime_or_safe_stop",
            "latest_log_clean",
            "latest_log_path",
            "save_as_path",
            "operator_name",
            "checked_at",
            "notes",
        ])
        writer.writeheader()
        writer.writerows(rows)


def required_row(payload: dict) -> dict:
    return [row for row in payload["rows"] if row["scenario"] == "37"][0]


def test_build_payload_blocks_empty_required_intake(tmp_path: Path) -> None:
    module = load_module()
    pack_path = tmp_path / "pack.json"
    intake_path = tmp_path / "intake.csv"
    write_pack(pack_path)
    write_intake(
        intake_path,
        [
            {"scenario": "37", "rks_path": r"C:\RK10\37.rks"},
            {"scenario": "12/13", "rks_path": ""},
        ],
    )

    payload = module.build_payload(pack_path, intake_path)

    assert payload["overall_rks_runtime_evidence_complete"] is False
    assert payload["row_count"] == 3
    assert payload["required_row_count"] == 1
    assert payload["approved_row_count"] == 0
    assert payload["needs_attention_count"] == 1
    assert "RK10_EDITOR_OPEN_NOT_CONFIRMED" in required_row(payload)["issue_codes"]
    deferred_row = [row for row in payload["rows"] if row["scenario"] == "44"][0]
    assert deferred_row["issue_codes"] == ""


def test_build_payload_approves_complete_runtime_evidence(tmp_path: Path) -> None:
    module = load_module()
    pack_path = tmp_path / "pack.json"
    intake_path = tmp_path / "intake.csv"
    log_path = tmp_path / "37-clean.log"
    log_path.write_text("RK10 editor open confirmed\nRK10 build confirmed\nsafe-stop confirmed\n", encoding="utf-8")
    write_pack(pack_path)
    write_intake(
        intake_path,
        [
            {
                "scenario": "37",
                "rks_path": r"C:\RK10\37.rks",
                "operator_decision": "SAFE_STOP_ONLY",
                "rk10_editor_open": "CONFIRMED",
                "rk10_build": "CONFIRMED",
                "runtime_or_safe_stop": "CONFIRMED",
                "latest_log_clean": "YES",
                "latest_log_path": str(log_path),
                "operator_name": "operator",
                "checked_at": "2026-06-20T15:30:00",
            },
            {"scenario": "12/13", "rks_path": ""},
        ],
    )

    payload = module.build_payload(pack_path, intake_path)

    assert payload["overall_rks_runtime_evidence_complete"] is True
    assert payload["approved_row_count"] == 1
    assert required_row(payload)["approved"] is True


def test_build_payload_blocks_hard_error_marker_in_latest_log(tmp_path: Path) -> None:
    module = load_module()
    pack_path = tmp_path / "pack.json"
    intake_path = tmp_path / "intake.csv"
    log_path = tmp_path / "37-error.log"
    log_path.write_text("RK10 build confirmed\nERROR: runtime failed\n", encoding="utf-8")
    write_pack(pack_path)
    write_intake(
        intake_path,
        [
            {
                "scenario": "37",
                "rks_path": r"C:\RK10\37.rks",
                "operator_decision": "SAFE_STOP_ONLY",
                "rk10_editor_open": "CONFIRMED",
                "rk10_build": "CONFIRMED",
                "runtime_or_safe_stop": "CONFIRMED",
                "latest_log_clean": "YES",
                "latest_log_path": str(log_path),
                "operator_name": "operator",
                "checked_at": "2026-06-20T15:30:00",
            },
        ],
    )

    payload = module.build_payload(pack_path, intake_path)

    assert payload["overall_rks_runtime_evidence_complete"] is False
    assert payload["hard_error_count"] == 1
    assert "LATEST_LOG_HAS_HARD_ERROR_MARKER" in required_row(payload)["issue_codes"]
