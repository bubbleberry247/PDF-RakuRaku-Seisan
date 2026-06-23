import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "collect_rk10_runtime_bundle_evidence_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("collect_rk10_runtime_bundle_evidence_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_validation(path: Path, latest_log: Path) -> None:
    payload = {
        "rows": [
            {
                "scenario": "37",
                "rks_path": r"C:\sample\37.rks",
                "requires_rk10_evidence": True,
                "operator_decision": "SAFE_STOP_ONLY",
                "rk10_editor_open": "CONFIRMED",
                "rk10_build": "CONFIRMED",
                "runtime_or_safe_stop": "CONFIRMED",
                "latest_log_clean": "YES",
                "latest_log_path": str(latest_log),
                "latest_log_path_exists": True,
                "latest_log_has_hard_errors": False,
                "operator_name": "operator",
                "checked_at": "2026-06-18T10:18:53",
                "approved": True,
                "issue_codes": "",
            },
            {
                "scenario": "57",
                "rks_path": r"C:\sample\57.rks",
                "requires_rk10_evidence": True,
                "approved": False,
                "latest_log_path": "",
                "issue_codes": "LATEST_LOG_PATH_MISSING_OR_NOT_FOUND",
            },
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_intake(path: Path, scenarios: tuple[str, ...] = ("37", "57")) -> None:
    fieldnames = [
        "bundle",
        "scenario",
        "required_final_evidence",
        "hard_stops",
        "current_reference_evidence",
        "suggested_final_evidence_folder",
        "final_evidence_path",
        "required_update_fields",
        "operator_result",
        "reviewer",
        "reviewed_at",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for scenario in scenarios:
            writer.writerow(
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenario": scenario,
                    "required_final_evidence": "metadata guard、open/build結果、safe-stopログ、latest clean log",
                    "hard_stops": "ButtonRun、本番書込、実メール",
                    "current_reference_evidence": r"C:\sample.md",
                    "suggested_final_evidence_folder": rf"C:\final\scenario_{scenario}",
                    "required_update_fields": "final_evidence_path, operator_result, reviewer, reviewed_at",
                }
            )


def write_intake_with_manual_reviewer(path: Path) -> None:
    write_intake(path, scenarios=("37",))
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            row["reviewer"] = "manual-reviewer"
            row["reviewed_at"] = "manual-reviewed-at"
            rows.append(row)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_intake_row(path: Path, scenario: str) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(row for row in csv.DictReader(handle) if row["scenario"] == scenario)


def test_build_result_collects_approved_rk10_runtime_evidence(tmp_path: Path) -> None:
    module = load_module()
    latest_log = tmp_path / "latest_log.txt"
    validation_path = tmp_path / "validation.json"
    intake_path = tmp_path / "intake.csv"
    final_root = tmp_path / "final"
    latest_log.write_text("clean", encoding="utf-8")
    write_validation(validation_path, latest_log)
    write_intake(intake_path)

    result = module.build_result(validation_path, intake_path, final_root)

    scenario_37 = next(row for row in result.scenarios if row.scenario == "37")
    assert result.status == "READY_FOR_REVIEWER_TIMESTAMP"
    assert result.approved_validator_count == 1
    assert result.appended_intake_row_count == 0
    assert result.collected_count == 1
    assert scenario_37.updated_intake is True
    assert len(scenario_37.final_evidence_files) == 2
    assert all(Path(path).exists() for path in scenario_37.final_evidence_files)
    row = read_intake_row(intake_path, "37")
    assert row["final_evidence_path"] == str(final_root / "scenario_37")
    assert row["operator_result"] == "OK"
    assert row["reviewer"] == "operator"
    assert row["reviewed_at"] == "2026-06-18T10:18:53"
    assert module.SYNC_NOTE in row["notes"]
    assert module.VALIDATOR_IDENTITY_SYNC_NOTE in row["notes"]


def test_build_result_appends_approved_row_missing_bundle_intake_row(tmp_path: Path) -> None:
    module = load_module()
    latest_log = tmp_path / "latest_log.txt"
    validation_path = tmp_path / "validation.json"
    intake_path = tmp_path / "intake.csv"
    latest_log.write_text("clean", encoding="utf-8")
    write_validation(validation_path, latest_log)
    write_intake(intake_path, scenarios=("57",))

    result = module.build_result(validation_path, intake_path, tmp_path / "final")

    scenario_37 = next(row for row in result.scenarios if row.scenario == "37")
    assert result.status == "READY_FOR_REVIEWER_TIMESTAMP"
    assert result.appended_intake_row_count == 1
    assert result.template_appended_row_count == 8
    assert scenario_37.updated_intake is True
    assert scenario_37.blockers == ""
    row = read_intake_row(intake_path, "37")
    assert row["final_evidence_path"] == str(tmp_path / "final" / "scenario_37")
    assert row["operator_result"] == "OK"
    assert row["reviewer"] == "operator"
    assert row["reviewed_at"] == "2026-06-18T10:18:53"
    assert module.AUTO_APPEND_NOTE in row["notes"]
    assert module.SYNC_NOTE in row["notes"]
    assert module.VALIDATOR_IDENTITY_SYNC_NOTE in row["notes"]
    template_path = intake_path.parent / "operator_evidence_filename_template.csv"
    template_text = template_path.read_text(encoding="utf-8-sig")
    assert "scenario_37_safe_stop_latest_clean_log_YYYYMMDD_HHMMSS.txt" in template_text
    assert "scenario_57_safe_stop_latest_clean_log_YYYYMMDD_HHMMSS.txt" in template_text
    assert template_path.with_suffix(".md").exists()


def test_build_result_keeps_existing_manual_reviewer_fields(tmp_path: Path) -> None:
    module = load_module()
    latest_log = tmp_path / "latest_log.txt"
    validation_path = tmp_path / "validation.json"
    intake_path = tmp_path / "intake.csv"
    latest_log.write_text("clean", encoding="utf-8")
    write_validation(validation_path, latest_log)
    write_intake_with_manual_reviewer(intake_path)

    result = module.build_result(validation_path, intake_path, tmp_path / "final")

    scenario_37 = next(row for row in result.scenarios if row.scenario == "37")
    assert scenario_37.updated_intake is True
    row = read_intake_row(intake_path, "37")
    assert row["reviewer"] == "manual-reviewer"
    assert row["reviewed_at"] == "manual-reviewed-at"
    assert module.SYNC_NOTE in row["notes"]
    assert module.VALIDATOR_IDENTITY_SYNC_NOTE not in row["notes"]
