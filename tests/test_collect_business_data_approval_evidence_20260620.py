import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "collect_business_data_approval_evidence_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("collect_business_data_approval_evidence_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_cost_map(path: Path, source_path: Path) -> None:
    payload = {
        "rows": [
            {
                "scenario": "47",
                "item_count": 9,
                "total_amount_yen": None,
                "source": str(source_path),
                "validation_result": "PASS_COUNT_ONLY",
            },
            {
                "scenario": "55",
                "item_count": 93,
                "total_amount_yen": 12938354,
                "source": str(source_path),
                "validation_result": "PASS",
            },
            {
                "scenario": "63",
                "item_count": 8,
                "total_amount_yen": 1205130,
                "source": str(source_path),
                "validation_result": "PASS",
            },
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_rks_validation(path: Path, scenario: str, latest_log_path: Path) -> None:
    payload = {
        "rows": [
            {
                "scenario": scenario,
                "requires_rk10_evidence": True,
                "approved": True,
                "latest_log_path": str(latest_log_path),
            }
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_approval(path: Path, source_path: Path, latest_log_path: Path, **overrides: str) -> None:
    fieldnames = [
        "scenario",
        "target_data_confirmed",
        "stop_condition_confirmed",
        "business_approver",
        "approved_item_count",
        "approved_total_amount_yen",
        "source_evidence_path",
        "latest_clean_log_path",
        "production_write_allowed_now",
        "mail_allowed_now",
        "payment_allowed_now",
    ]
    row = {
        "scenario": "55",
        "target_data_confirmed": "OK",
        "stop_condition_confirmed": "OK",
        "business_approver": "APPROVER_BUSINESS",
        "approved_item_count": "93",
        "approved_total_amount_yen": "12938354",
        "source_evidence_path": str(source_path),
        "latest_clean_log_path": str(latest_log_path),
        "production_write_allowed_now": "NO",
        "mail_allowed_now": "NO",
        "payment_allowed_now": "NO",
        **overrides,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def write_intake(path: Path) -> None:
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
        for scenario in ("43", "47", "55", "63"):
            writer.writerow(
                {
                    "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                    "scenario": scenario,
                    "required_final_evidence": "対象データ、dry-runログ、停止位置、件数/金額、latest clean log",
                    "hard_stops": "本番登録、実メール、本番Excel/サーバ確定書込、支払処理",
                    "current_reference_evidence": r"C:\sample.md",
                    "suggested_final_evidence_folder": rf"C:\final\scenario_{scenario}",
                    "required_update_fields": "final_evidence_path, operator_result, reviewer, reviewed_at",
                }
            )


def read_intake_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_result_waits_when_approval_csv_is_missing(tmp_path: Path) -> None:
    module = load_module()
    cost_map_path = tmp_path / "cost.json"
    intake_path = tmp_path / "intake.csv"
    source_path = tmp_path / "source.txt"
    source_path.write_text("source", encoding="utf-8")
    write_cost_map(cost_map_path, source_path)
    write_intake(intake_path)

    result = module.build_result(
        tmp_path / "missing.csv",
        cost_map_path,
        intake_path,
        tmp_path / "final",
    )

    assert result.status == "WAITING_FOR_BUSINESS_DATA_APPROVAL"
    assert result.ready_scenario_count == 0
    assert result.updated_scenario_count == 0
    assert all("APPROVAL_ROW_MISSING" in row.blockers for row in result.scenarios)
    assert all(row["final_evidence_path"] == "" for row in read_intake_rows(intake_path))


def test_ensure_approval_csv_template_prefills_known_costs_without_approval(
    tmp_path: Path,
) -> None:
    module = load_module()
    approval_path = tmp_path / "approval.csv"
    cost_map_path = tmp_path / "cost.json"
    intake_path = tmp_path / "intake.csv"
    source_path = tmp_path / "source.txt"
    source_path.write_text("source", encoding="utf-8")
    write_cost_map(cost_map_path, source_path)
    write_intake(intake_path)

    created = module.ensure_approval_csv_template(approval_path, cost_map_path)
    result = module.build_result(
        approval_path,
        cost_map_path,
        intake_path,
        tmp_path / "final",
        approval_template_created=created,
    )

    approval_rows = read_intake_rows(approval_path)
    row_55 = next(row for row in approval_rows if row["scenario"] == "55")
    row_43 = next(row for row in approval_rows if row["scenario"] == "43")
    scenario_55 = next(row for row in result.scenarios if row.scenario == "55")

    assert created is True
    assert result.approval_template_created is True
    assert result.status == "WAITING_FOR_BUSINESS_DATA_APPROVAL"
    assert row_55["approved_item_count"] == "93"
    assert row_55["approved_total_amount_yen"] == "12938354"
    assert row_55["source_evidence_path"] == str(source_path)
    assert row_55["latest_clean_log_path"] == str(source_path)
    assert row_43["approved_item_count"] == "TODO_ITEM_COUNT"
    assert row_43["production_write_allowed_now"] == "NO"
    assert scenario_55.updated_intake is False
    assert "TARGET_DATA_NOT_CONFIRMED" in scenario_55.blockers
    assert "BUSINESS_APPROVER_NOT_FILLED" in scenario_55.blockers


def test_ensure_approval_csv_template_uses_approved_rks_log_without_approving(
    tmp_path: Path,
) -> None:
    module = load_module()
    approval_path = tmp_path / "approval.csv"
    cost_map_path = tmp_path / "cost.json"
    rks_validation_path = tmp_path / "rks_validation.json"
    intake_path = tmp_path / "intake.csv"
    source_path = tmp_path / "source.txt"
    rks_log_path = tmp_path / "s47.status_gate.md.numbered"
    source_path.write_text("source", encoding="utf-8")
    rks_log_path.write_text("safe stop clean", encoding="utf-8")
    write_cost_map(cost_map_path, source_path)
    write_rks_validation(rks_validation_path, "47", rks_log_path)
    write_intake(intake_path)

    created = module.ensure_approval_csv_template(
        approval_path,
        cost_map_path,
        rks_validation_path,
    )
    result = module.build_result(
        approval_path,
        cost_map_path,
        intake_path,
        tmp_path / "final",
        rks_validation_path,
        approval_template_created=created,
    )
    approval_rows = read_intake_rows(approval_path)
    row_47 = next(row for row in approval_rows if row["scenario"] == "47")
    scenario_47 = next(row for row in result.scenarios if row.scenario == "47")

    assert created is True
    assert row_47["latest_clean_log_path"] == str(rks_log_path)
    assert row_47["approved_total_amount_yen"] == "TODO_TOTAL_AMOUNT_YEN"
    assert scenario_47.latest_clean_log_exists is True
    assert scenario_47.updated_intake is False
    assert "BUSINESS_APPROVER_NOT_FILLED" in scenario_47.blockers
    assert "APPROVED_TOTAL_AMOUNT_NOT_FILLED" in scenario_47.blockers


def test_prefill_existing_approval_csv_adds_safe_log_without_overwriting_human_fields(
    tmp_path: Path,
) -> None:
    module = load_module()
    approval_path = tmp_path / "approval.csv"
    cost_map_path = tmp_path / "cost.json"
    source_path = tmp_path / "source.txt"
    human_log_path = tmp_path / "human.log"
    source_path.write_text("source", encoding="utf-8")
    human_log_path.write_text("human clean", encoding="utf-8")
    write_cost_map(cost_map_path, source_path)
    fieldnames = module.APPROVAL_FIELDNAMES
    approval_rows = [
        {
            "scenario": "55",
            "target_data_confirmed": "TODO_CONFIRM_TARGET_DATA",
            "stop_condition_confirmed": "TODO_CONFIRM_STOP_CONDITION",
            "business_approver": "TODO_APPROVER",
            "approved_item_count": "TODO_ITEM_COUNT",
            "approved_total_amount_yen": "TODO_TOTAL_AMOUNT_YEN",
            "source_evidence_path": "TODO_SOURCE_EVIDENCE_PATH",
            "latest_clean_log_path": "TODO_LATEST_CLEAN_LOG_PATH",
            "production_write_allowed_now": "NO",
            "mail_allowed_now": "NO",
            "payment_allowed_now": "NO",
        },
        {
            "scenario": "63",
            "target_data_confirmed": "TODO_CONFIRM_TARGET_DATA",
            "stop_condition_confirmed": "TODO_CONFIRM_STOP_CONDITION",
            "business_approver": "TODO_APPROVER",
            "approved_item_count": "8",
            "approved_total_amount_yen": "1205130",
            "source_evidence_path": str(human_log_path),
            "latest_clean_log_path": str(human_log_path),
            "production_write_allowed_now": "NO",
            "mail_allowed_now": "NO",
            "payment_allowed_now": "NO",
        },
    ]
    module.write_csv_rows(approval_path, fieldnames, approval_rows)

    updated_count = module.prefill_existing_approval_csv_from_cost_map(
        approval_path,
        cost_map_path,
    )
    rows = read_intake_rows(approval_path)
    row_55 = next(row for row in rows if row["scenario"] == "55")
    row_63 = next(row for row in rows if row["scenario"] == "63")

    assert updated_count == 1
    assert row_55["approved_item_count"] == "93"
    assert row_55["approved_total_amount_yen"] == "12938354"
    assert row_55["source_evidence_path"] == str(source_path)
    assert row_55["latest_clean_log_path"] == str(source_path)
    assert row_55["business_approver"] == "TODO_APPROVER"
    assert row_63["source_evidence_path"] == str(human_log_path)
    assert row_63["latest_clean_log_path"] == str(human_log_path)


def test_build_result_collects_ready_business_data_row(tmp_path: Path) -> None:
    module = load_module()
    approval_path = tmp_path / "approval.csv"
    cost_map_path = tmp_path / "cost.json"
    intake_path = tmp_path / "intake.csv"
    source_path = tmp_path / "source.txt"
    latest_log_path = tmp_path / "latest.log"
    final_root = tmp_path / "final"
    source_path.write_text("source", encoding="utf-8")
    latest_log_path.write_text("clean", encoding="utf-8")
    write_cost_map(cost_map_path, source_path)
    write_approval(approval_path, source_path, latest_log_path)
    write_intake(intake_path)

    result = module.build_result(approval_path, cost_map_path, intake_path, final_root)

    scenario_55 = next(row for row in result.scenarios if row.scenario == "55")
    assert result.status == "PARTIAL_READY_FOR_OPERATOR_FINAL_FIELDS"
    assert scenario_55.status == "READY_FOR_OPERATOR_FINAL_FIELDS"
    assert scenario_55.ready_for_intake is True
    assert scenario_55.updated_intake is True
    assert scenario_55.count_difference == 0
    assert scenario_55.amount_difference_yen == 0
    assert len(scenario_55.final_evidence_files) == 2
    assert all(Path(path).exists() for path in scenario_55.final_evidence_files)
    row_55 = next(row for row in read_intake_rows(intake_path) if row["scenario"] == "55")
    assert row_55["final_evidence_path"] == str(final_root / "scenario_55")
    assert row_55["operator_result"] == ""
    assert row_55["reviewer"] == ""
    assert module.SYNC_NOTE in row_55["notes"]


def test_build_result_blocks_unsafe_production_write_flag(tmp_path: Path) -> None:
    module = load_module()
    approval_path = tmp_path / "approval.csv"
    cost_map_path = tmp_path / "cost.json"
    intake_path = tmp_path / "intake.csv"
    source_path = tmp_path / "source.txt"
    latest_log_path = tmp_path / "latest.log"
    source_path.write_text("source", encoding="utf-8")
    latest_log_path.write_text("clean", encoding="utf-8")
    write_cost_map(cost_map_path, source_path)
    write_approval(approval_path, source_path, latest_log_path, production_write_allowed_now="YES")
    write_intake(intake_path)

    result = module.build_result(approval_path, cost_map_path, intake_path, tmp_path / "final")

    scenario_55 = next(row for row in result.scenarios if row.scenario == "55")
    assert scenario_55.status == "WAITING_FOR_BUSINESS_DATA_APPROVAL"
    assert "PRODUCTION_WRITE_ALLOWED_FLAG_IS_UNSAFE" in scenario_55.blockers
    assert scenario_55.updated_intake is False
