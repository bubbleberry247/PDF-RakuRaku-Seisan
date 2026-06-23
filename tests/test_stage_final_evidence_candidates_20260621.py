import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "stage_final_evidence_candidates_20260621.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "stage_final_evidence_candidates_20260621",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def intake_fieldnames() -> list[str]:
    return [
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
        "rakuraku_customer_login_used",
        "temporary_save_created",
        "created_data_cleanup_status",
        "created_data_cleanup_evidence_path",
        "cleanup_reviewer",
        "cleanup_reviewed_at",
        "notes",
    ]


def operator_sheet_fieldnames() -> list[str]:
    return [
        "bundle",
        "owner",
        "scenarios",
        "scenario_count",
        "approval_scope",
        "allowed_operations",
        "evidence_to_capture",
        "hard_stops",
        "packet_csv_path",
        "prepared_evidence_pack_path",
        "operator_result",
        "evidence_path",
        "reviewer",
        "reviewed_at",
        "rakuraku_customer_login_used",
        "temporary_save_created",
        "created_data_cleanup_status",
        "created_data_cleanup_evidence_path",
        "cleanup_reviewer",
        "cleanup_reviewed_at",
        "notes",
    ]


def make_pack(
    tmp_path: Path,
    source_path: Path,
    bundle: str = "PAYMENT_APPROVAL_BUNDLE",
    scenario: str = "70",
) -> tuple[Path, Path, Path, Path]:
    pack_dir = tmp_path / bundle.lower()
    final_dir = pack_dir / "final_evidence"
    scenario_dir = final_dir / f"scenario_{scenario}"
    intake_path = pack_dir / "final_evidence_intake.csv"
    template_path = pack_dir / "operator_evidence_filename_template.csv"
    write_csv(
        intake_path,
        intake_fieldnames(),
        [
            {
                "bundle": bundle,
                "scenario": scenario,
                "required_final_evidence": "preview log",
                "hard_stops": "no execute",
                "current_reference_evidence": str(source_path),
                "suggested_final_evidence_folder": str(scenario_dir),
                "final_evidence_path": "",
                "required_update_fields": "final_evidence_path, operator_result, reviewer, reviewed_at",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "notes": "",
            }
        ],
    )
    write_csv(
        template_path,
        [
            "bundle",
            "scenario",
            "template_only_not_final_evidence",
            "save_under_folder",
            "evidence_kind",
            "example_filename",
            "purpose",
            "notes",
        ],
        [
            {
                "bundle": bundle,
                "scenario": scenario,
                "template_only_not_final_evidence": "YES",
                "save_under_folder": str(scenario_dir),
                "evidence_kind": "log",
                "example_filename": f"scenario_{scenario}_safe_run_log_YYYYMMDD_HHMMSS.txt",
                "purpose": "Safe run log",
                "notes": "template only",
            }
        ],
    )
    pack_json = tmp_path / "bundle_evidence_packs.json"
    pack_json.write_text(
        json.dumps(
            {
                "packs": [
                    {
                        "bundle": bundle,
                        "scenarios": scenario,
                        "scenario_count": 1,
                        "intake_path": str(intake_path),
                        "filename_template_path": str(template_path),
                        "final_evidence_dir": str(final_dir),
                        "scenario_evidence": [
                            {
                                "scenario": scenario,
                                "current_reference_evidence": str(source_path),
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    write_csv(
        operator_sheet,
        operator_sheet_fieldnames(),
        [
            {
                "bundle": bundle,
                "owner": "支払承認者",
                "scenarios": scenario,
                "scenario_count": "1",
                "approval_scope": "preview only",
                "allowed_operations": "confirm-preview",
                "evidence_to_capture": "preview log",
                "hard_stops": "no execute",
                "packet_csv_path": str(tmp_path / "payment.csv"),
                "prepared_evidence_pack_path": str(pack_dir),
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
                "notes": "",
            }
        ],
    )
    return pack_json, operator_sheet, intake_path, final_dir


def test_stage_candidates_copies_reference_and_prefills_paths_only(tmp_path: Path) -> None:
    module = load_module()
    source_path = tmp_path / "source_report.md"
    source_path.write_text("safe preview completed", encoding="utf-8")
    pack_json, operator_sheet, intake_path, final_dir = make_pack(tmp_path, source_path)

    payload = module.build_payload(pack_json, operator_sheet, apply_updates=True)

    intake_rows = read_csv(intake_path)
    operator_rows = read_csv(operator_sheet)
    staged_files = list((final_dir / "scenario_70").glob("scenario_70_safe_run_log_*.txt"))
    assert payload["staged_count"] == 1
    assert len(staged_files) == 1
    assert "safe preview completed" in staged_files[0].read_text(encoding="utf-8")
    assert intake_rows[0]["final_evidence_path"] == str(final_dir / "scenario_70")
    assert intake_rows[0]["operator_result"] == ""
    assert operator_rows[0]["evidence_path"] == str(final_dir)
    assert operator_rows[0]["operator_result"] == ""
    assert operator_rows[0]["reviewer"] == ""
    assert operator_rows[0]["reviewed_at"] == ""


def test_stage_candidates_does_not_override_existing_operator_sheet_evidence_path(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_path = tmp_path / "source_report.md"
    source_path.write_text("safe preview completed", encoding="utf-8")
    pack_json, operator_sheet, _intake_path, _final_dir = make_pack(tmp_path, source_path)
    rows = read_csv(operator_sheet)
    rows[0]["evidence_path"] = str(tmp_path / "already_selected")
    rows[0]["notes"] = "manual_path"
    write_csv(operator_sheet, operator_sheet_fieldnames(), rows)

    payload = module.build_payload(pack_json, operator_sheet, apply_updates=True)

    operator_rows = read_csv(operator_sheet)
    assert payload["operator_sheet_updated_count"] == 0
    assert operator_rows[0]["evidence_path"].endswith("already_selected")
    assert operator_rows[0]["notes"] == "manual_path"


def test_stage_candidates_is_idempotent_for_same_source(tmp_path: Path) -> None:
    module = load_module()
    source_path = tmp_path / "source_report.md"
    source_path.write_text("safe preview completed", encoding="utf-8")
    pack_json, operator_sheet, _intake_path, final_dir = make_pack(tmp_path, source_path)

    first_payload = module.build_payload(pack_json, operator_sheet, apply_updates=True)
    second_payload = module.build_payload(pack_json, operator_sheet, apply_updates=True)

    staged_files = list((final_dir / "scenario_70").glob("scenario_70_safe_run_log_*.txt"))
    assert first_payload["staged_count"] == 1
    assert second_payload["staged_count"] == 1
    assert second_payload["changed_file_count"] == 0
    assert len(staged_files) == 1


def test_stage_candidates_leaves_rk10_operator_bundle_path_blank(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_path = tmp_path / "rk10_status_gate.md"
    source_path.write_text("rk10 status gate evidence", encoding="utf-8")
    pack_json, operator_sheet, intake_path, final_dir = make_pack(
        tmp_path,
        source_path,
        bundle="RK10_EDITOR_RUNTIME_BUNDLE",
        scenario="37",
    )

    payload = module.build_payload(pack_json, operator_sheet, apply_updates=True)

    intake_rows = read_csv(intake_path)
    operator_rows = read_csv(operator_sheet)
    staged_files = list((final_dir / "scenario_37").glob("scenario_37_safe_run_log_*.txt"))
    assert payload["staged_count"] == 1
    assert len(staged_files) == 1
    assert intake_rows[0]["final_evidence_path"] == str(final_dir / "scenario_37")
    assert intake_rows[0]["operator_result"] == ""
    assert operator_rows[0]["evidence_path"] == ""
    assert operator_rows[0]["operator_result"] == ""
    assert operator_rows[0]["reviewer"] == ""
    assert operator_rows[0]["reviewed_at"] == ""


def test_stage_candidates_clears_prior_autofilled_rk10_operator_bundle_path(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_path = tmp_path / "rk10_status_gate.md"
    source_path.write_text("rk10 status gate evidence", encoding="utf-8")
    pack_json, operator_sheet, _intake_path, final_dir = make_pack(
        tmp_path,
        source_path,
        bundle="RK10_EDITOR_RUNTIME_BUNDLE",
        scenario="37",
    )
    rows = read_csv(operator_sheet)
    rows[0]["evidence_path"] = str(final_dir)
    rows[0]["notes"] = module.SYNC_NOTE
    write_csv(operator_sheet, operator_sheet_fieldnames(), rows)

    payload = module.build_payload(pack_json, operator_sheet, apply_updates=True)

    operator_rows = read_csv(operator_sheet)
    assert payload["operator_sheet_updated_count"] == 1
    assert operator_rows[0]["evidence_path"] == ""
    assert "rk10_bundle_path_left_blank_due_template_scope" in operator_rows[0]["notes"]
    assert operator_rows[0]["operator_result"] == ""
    assert operator_rows[0]["reviewer"] == ""
    assert operator_rows[0]["reviewed_at"] == ""
