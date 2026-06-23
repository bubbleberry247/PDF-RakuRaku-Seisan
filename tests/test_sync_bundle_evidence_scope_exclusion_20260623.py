import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "sync_bundle_evidence_intake_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "sync_bundle_evidence_intake_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_scope_exclusion_filters_scenario_before_bundle_sync(tmp_path: Path) -> None:
    module = load_module()
    bundle = "BUSINESS_DATA_APPROVAL_BUNDLE"
    pack_dir = tmp_path / "pack" / "business_data"
    final_dir = pack_dir / "final_evidence"
    scenario_47_dir = final_dir / "scenario_47"
    scenario_47_dir.mkdir(parents=True)
    scenario_47_file = (
        scenario_47_dir / "scenario_47_safe_stop_latest_clean_log_20260621_120000.txt"
    )
    scenario_47_file.write_text("ok", encoding="utf-8")
    intake_path = pack_dir / "final_evidence_intake.csv"
    filename_template_path = pack_dir / "operator_evidence_filename_template.csv"
    filename_template_path.write_text(
        "\n".join(
            [
                "bundle,scenario,template_only_not_final_evidence,save_under_folder,evidence_kind,example_filename,purpose,notes",
                f"{bundle},47,YES,{scenario_47_dir},log,scenario_47_safe_stop_latest_clean_log_YYYYMMDD_HHMMSS.txt,Safe-stop runtime latest clean log,Template only",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )
    write_csv(
        intake_path,
        [
            {
                "bundle": bundle,
                "scenario": "43",
                "required_final_evidence": "final log",
                "current_reference_evidence": "",
                "final_evidence_path": str(final_dir / "scenario_43" / "missing.txt"),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "rakuraku_customer_login_used": "",
                "temporary_save_created": "",
                "created_data_cleanup_status": "",
                "created_data_cleanup_evidence_path": "",
                "cleanup_reviewer": "",
                "cleanup_reviewed_at": "",
                "notes": "",
            },
            {
                "bundle": bundle,
                "scenario": "47",
                "required_final_evidence": "final log",
                "current_reference_evidence": "",
                "final_evidence_path": str(scenario_47_file),
                "operator_result": "OK",
                "reviewer": "field-user",
                "reviewed_at": "2026-06-23T15:18:00",
                "rakuraku_customer_login_used": "",
                "temporary_save_created": "",
                "created_data_cleanup_status": "",
                "created_data_cleanup_evidence_path": "",
                "cleanup_reviewer": "",
                "cleanup_reviewed_at": "",
                "notes": "",
            },
        ],
    )
    pack = {
        "bundle": bundle,
        "scenarios": "43,47",
        "scenario_count": 2,
        "pack_dir": str(pack_dir),
        "intake_path": str(intake_path),
        "filename_template_path": str(filename_template_path),
        "final_evidence_dir": str(final_dir),
    }
    pack_json = tmp_path / "bundle_evidence_packs.json"
    pack_json.write_text(
        json.dumps({"packs": [pack]}, ensure_ascii=False),
        encoding="utf-8",
    )
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    write_csv(
        operator_sheet,
        [
            {
                "bundle": bundle,
                "owner": "業務担当者",
                "scenarios": "43,47",
                "scenario_count": "2",
                "approval_scope": "",
                "allowed_operations": "",
                "evidence_to_capture": "",
                "hard_stops": "",
                "packet_csv_path": "",
                "prepared_evidence_pack_path": "",
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
                "rakuraku_customer_login_used": "",
                "temporary_save_created": "",
                "created_data_cleanup_status": "",
                "created_data_cleanup_evidence_path": "",
                "cleanup_reviewer": "",
                "cleanup_reviewed_at": "",
                "notes": "",
            }
        ],
    )
    scope_exclusions_json = tmp_path / "scope_exclusions.json"
    scope_exclusions_json.write_text(
        json.dumps(
            {"exclusions": [{"scenario": "43", "active": True}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = module.build_payload(
        pack_json,
        operator_sheet,
        apply_updates=True,
        scope_exclusions_json=scope_exclusions_json,
    )

    result = payload["results"][0]
    assert payload["scope_excluded_scenarios"] == ["43"]
    assert payload["ready_to_sync_count"] == 1
    assert result["scenario_count"] == 1
    assert result["intake_row_count"] == 1
    assert result["ready_row_count"] == 1
    assert result["ready_to_sync"] is True
    with operator_sheet.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = {row["bundle"]: row for row in csv.DictReader(handle)}
    assert rows[bundle]["operator_result"] == "OK"
    assert rows[bundle]["evidence_path"] == str(scenario_47_file)
