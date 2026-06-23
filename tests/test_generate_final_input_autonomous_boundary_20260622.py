import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_final_input_autonomous_boundary_20260622.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_final_input_autonomous_boundary_20260622",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def base_row(tmp_path: Path) -> dict[str, str]:
    final_folder = tmp_path / "final" / "scenario_44"
    final_folder.mkdir(parents=True, exist_ok=True)
    return {
        "bundle": "BUSINESS_REVIEW_BUNDLE",
        "scenario": "44",
        "hard_stops": "本番登録",
        "still_forbidden": "最終申請",
        "suggested_final_evidence_folder": str(final_folder),
        "final_evidence_path": str(final_folder),
        "operator_result": "",
        "reviewer": "",
        "reviewed_at": "",
        "source_intake_path": str(tmp_path / "intake.csv"),
    }


def test_build_payload_classifies_filled_and_human_rows(tmp_path: Path) -> None:
    module = load_module()
    unified_csv = tmp_path / "unified.csv"
    human_row = base_row(tmp_path)
    filled_row = {
        **base_row(tmp_path),
        "bundle": "OUTLOOK_COM_BUNDLE",
        "scenario": "12/13",
        "operator_result": "OK",
        "reviewer": "codex_safe_dryrun_20260622",
        "reviewed_at": "2026-06-22T20:27:00",
    }
    write_csv(unified_csv, [human_row, filled_row])

    payload = module.build_payload(unified_csv)

    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["filled_row_count"] == 1
    assert payload["summary"]["missing_final_input_row_count"] == 1
    assert payload["summary"]["auto_approval_performed"] is False
    assert (
        payload["summary"]["boundary_counts"][
            "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL"
        ]
        == 1
    )
    assert (
        payload["summary"]["boundary_counts"]["FILLED_READY_FOR_VALIDATION_SYNC"]
        == 1
    )
    human_payload = payload["rows"][0]
    assert human_payload["missing_fields"] == "operator_result, reviewer, reviewed_at"
    assert human_payload["final_evidence_path_exists"] == "YES"
    assert "人手承認" in human_payload["human_or_external_input_needed"]


def test_build_payload_marks_rk10_as_safe_technical_not_approved(
    tmp_path: Path,
) -> None:
    module = load_module()
    unified_csv = tmp_path / "unified.csv"
    row = {
        **base_row(tmp_path),
        "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
        "scenario": "42",
        "hard_stops": "ButtonRun、本番書込",
        "still_forbidden": "RK10 ButtonRun",
    }
    write_csv(unified_csv, [row])

    payload = module.build_payload(unified_csv)

    assert payload["summary"]["safe_technical_evidence_can_continue_count"] == 1
    boundary_row = payload["rows"][0]
    assert (
        boundary_row["boundary_class"]
        == "SAFE_TECHNICAL_EVIDENCE_CAN_CONTINUE_NO_AUTO_APPROVAL"
    )
    assert "既定ラジオを触らずOKのみ" in boundary_row["codex_can_continue_with"]
    assert "ButtonRun" in boundary_row["forbidden_scope"]


def test_build_payload_moves_deferred_rk10_to_human_decision_boundary(
    tmp_path: Path,
) -> None:
    module = load_module()
    unified_csv = tmp_path / "unified.csv"
    rks_matrix_json = tmp_path / "rks_gate_matrix.json"
    row = {
        **base_row(tmp_path),
        "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
        "scenario": "42",
        "hard_stops": "ButtonRun、本番書込",
        "still_forbidden": "RK10 ButtonRun",
    }
    write_csv(unified_csv, [row])
    write_json(
        rks_matrix_json,
        {
            "rows": [
                {
                    "scenario": "42",
                    "runtime_intake_status": (
                        "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION"
                    ),
                }
            ]
        },
    )

    payload = module.build_payload(unified_csv, rks_matrix_json)

    assert payload["summary"]["safe_technical_evidence_can_continue_count"] == 0
    assert (
        payload["summary"]["human_or_external_approval_required_count"]
        == 1
    )
    boundary_row = payload["rows"][0]
    assert (
        boundary_row["boundary_class"]
        == "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL"
    )
    assert "RKS要否" in boundary_row["human_or_external_input_needed"]
    assert "既定ラジオを触らずOKのみ" in boundary_row["codex_can_continue_with"]


def test_build_payload_excludes_active_scope_exclusion_rows(tmp_path: Path) -> None:
    module = load_module()
    unified_csv = tmp_path / "unified.csv"
    scope_exclusions_json = tmp_path / "scope_exclusions.json"
    excluded_row = {
        **base_row(tmp_path),
        "scenario": "43",
    }
    active_row = {
        **base_row(tmp_path),
        "scenario": "44",
    }
    write_csv(unified_csv, [excluded_row, active_row])
    write_json(
        scope_exclusions_json,
        {
            "exclusions": [
                {
                    "scenario": "43",
                    "active": True,
                    "reason": "external fix",
                }
            ]
        },
    )

    payload = module.build_payload(
        unified_csv,
        scope_exclusions_json=scope_exclusions_json,
    )

    assert payload["summary"]["raw_row_count"] == 2
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["excluded_row_count"] == 1
    assert payload["summary"]["missing_final_input_row_count"] == 1
    assert payload["rows"][0]["scenario"] == "44"
    assert payload["excluded_rows"][0]["scenario"] == "43"
