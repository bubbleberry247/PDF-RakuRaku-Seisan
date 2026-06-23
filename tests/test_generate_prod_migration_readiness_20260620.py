import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_prod_migration_readiness_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_prod_migration_readiness_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def base_sources(tmp_path: Path) -> dict[str, Path]:
    return {
        "safe_runner": write_json(tmp_path / "safe_runner.json", {"overall_passed": True}),
        "code_artifact_backup": write_json(
            tmp_path / "code_backup.json",
            {"backup_complete": True, "artifact_count": 2, "missing_count": 0},
        ),
        "status_snapshot": write_json(
            tmp_path / "status_snapshot.json",
            {
                "scenarios": [
                    {
                        "scenario": "43",
                        "current_status": "SCOPED_CONFIRMED_AFTER_FEEDBACK",
                        "source": str(tmp_path / "s43.md"),
                        "source_exists": True,
                        "remaining_gate": "final click boundary",
                        "next_action": "final click remains human",
                    },
                    {
                        "scenario": "57",
                        "current_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                        "source": str(tmp_path / "s57.md"),
                        "source_exists": True,
                        "remaining_gate": "safe-stop clean log",
                        "next_action": "rerun safe-stop",
                    },
                ]
            },
        ),
        "sample_data_map": write_json(
            tmp_path / "sample.json",
            {
                "rows": [
                    {
                        "scenario": "43",
                        "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                        "artifact_paths": str(tmp_path / "s43_sample.log"),
                    },
                    {
                        "scenario": "57",
                        "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                        "artifact_paths": str(tmp_path / "s57_sample.log"),
                    },
                ]
            },
        ),
        "safe_execution_map": write_json(
            tmp_path / "safe_execution.json",
            {
                "rows": [
                    {
                        "scenario": "43",
                        "safe_suite_status": "SAFE_SUITE_EXIT0_STDERR0",
                        "stdout_paths": str(tmp_path / "s43.stdout.txt"),
                        "stderr_paths": str(tmp_path / "s43.stderr.txt"),
                    },
                    {
                        "scenario": "57",
                        "safe_suite_status": "SAFE_SUITE_EXIT0_STDERR0",
                        "stdout_paths": str(tmp_path / "s57.stdout.txt"),
                        "stderr_paths": str(tmp_path / "s57.stderr.txt"),
                    },
                ]
            },
        ),
        "business_cost_map": write_json(
            tmp_path / "cost.json",
            {
                "rows": [
                    {
                        "scenario": "43",
                        "cost_evidence_status": "NOT_SUMMARIZED_IN_THIS_COST_MAP",
                        "validation_result": "NOT_PROVEN_IN_COST_MAP",
                        "source": str(tmp_path / "safe_execution.json"),
                    },
                    {
                        "scenario": "57",
                        "cost_evidence_status": "NOT_SUMMARIZED_IN_THIS_COST_MAP",
                        "validation_result": "NOT_PROVEN_IN_COST_MAP",
                        "source": str(tmp_path / "safe_execution.json"),
                    },
                ]
            },
        ),
        "rks_matrix": write_json(
            tmp_path / "rks.json",
            {
                "rows": [
                    {
                        "scenario": "57",
                        "current_rks_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                        "runtime_intake_status": "RKS_RUNTIME_EVIDENCE_PENDING",
                        "missing_gate": "runtime safe-stop latest clean log",
                        "next_safe_action": "rerun safe-stop",
                        "primary_source": str(tmp_path / "rks57.md"),
                    }
                ]
            },
        ),
        "bundle_evidence_validation": write_json(
            tmp_path / "bundle_validation.json",
            {"checks": []},
        ),
        "outlook_bundle_evidence_collect": write_json(
            tmp_path / "outlook_collect.json",
            {},
        ),
    }


def test_build_payload_separates_migration_ready_from_final_execution(tmp_path: Path) -> None:
    module = load_module()

    payload = module.build_payload(base_sources(tmp_path))

    assert payload["prod_migration_ok"] is False
    assert payload["migration_ready_count"] == 1
    assert payload["blocked_scenario_count"] == 1
    ready_row = [row for row in payload["rows"] if row["scenario"] == "43"][0]
    blocked_row = [row for row in payload["rows"] if row["scenario"] == "57"][0]
    assert ready_row["migration_ready"] is True
    assert ready_row["rks_gate"] == "RKS_NOT_REQUIRED"
    assert blocked_row["migration_ready"] is False
    assert "RKS_GATE_NOT_READY" in blocked_row["blockers"]


def test_build_payload_global_backup_failure_blocks_all_rows(tmp_path: Path) -> None:
    module = load_module()
    sources = base_sources(tmp_path)
    write_json(
        sources["code_artifact_backup"],
        {"backup_complete": False, "artifact_count": 2, "missing_count": 1},
    )

    payload = module.build_payload(sources)

    assert payload["migration_ready_count"] == 0
    assert payload["blocked_scenario_count"] == 2
    assert all("CODE_BACKUP_INCOMPLETE" in row["blockers"] for row in payload["rows"])


def test_build_payload_accepts_outlook_bundle_safe_evidence_for_12_13(tmp_path: Path) -> None:
    module = load_module()
    sources = base_sources(tmp_path)
    safe_evidence_path = str(tmp_path / "outlook_com_bundle" / "final_evidence" / "scenario_12_13")
    write_json(
        sources["status_snapshot"],
        {
            "scenarios": [
                {
                    "scenario": "12/13",
                    "current_status": "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
                    "source": str(tmp_path / "s12_13.md"),
                    "source_exists": True,
                    "next_action": "keep no-print/no-mail boundary",
                }
            ]
        },
    )
    write_json(
        sources["sample_data_map"],
        {
            "rows": [
                {
                    "scenario": "12/13",
                    "sample_data_status": "OUTLOOK_COM_HOLD_SAMPLE_REFRESH_REQUIRED",
                    "artifact_paths": str(tmp_path / "old_sample_hold.md"),
                }
            ]
        },
    )
    write_json(
        sources["safe_execution_map"],
        {
            "rows": [
                {
                    "scenario": "12/13",
                    "safe_suite_status": "NOT_IN_SAFE_SUITE_OUTLOOK_COM_HOLD",
                    "stdout_paths": str(tmp_path / "old_safe_hold.md"),
                }
            ]
        },
    )
    write_json(
        sources["business_cost_map"],
        {
            "rows": [
                {
                    "scenario": "12/13",
                    "cost_evidence_status": "OUTLOOK_COM_DRYRUN_COUNT_PROOF_NO_PRINT_NO_MAIL",
                    "validation_result": "PASS_COUNT_ONLY",
                    "source": str(tmp_path / "cost.csv"),
                }
            ]
        },
    )
    write_json(
        sources["rks_matrix"],
        {
            "rows": [
                {
                    "scenario": "12/13",
                    "current_rks_status": "N_A_NO_PRIMARY_RKS",
                    "runtime_intake_status": "N_A_NO_PRIMARY_RKS",
                    "primary_source": str(tmp_path / "rks_not_applicable.md"),
                }
            ]
        },
    )
    write_json(
        sources["bundle_evidence_validation"],
        {
            "checks": [
                {
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "scenarios": "12/13",
                    "final_evidence_ready": False,
                    "final_evidence_path": "",
                }
            ]
        },
    )
    write_json(
        sources["outlook_bundle_evidence_collect"],
        {
            "status": "READY_FOR_FINAL_EVIDENCE_INTAKE",
            "ready_for_intake": True,
            "evidence_path": safe_evidence_path,
            "log_status": {
                "check_exit": "0",
                "scan_exit": "0",
            },
        },
    )

    payload = module.build_payload(sources)

    assert payload["migration_ready_count"] == 1
    assert payload["blocked_scenario_count"] == 0
    row = payload["rows"][0]
    assert row["scenario"] == "12/13"
    assert row["migration_ready"] is True
    assert row["sample_gate"] == module.OUTLOOK_COM_SAMPLE_READY_STATUS
    assert row["safe_execution_gate"] == module.OUTLOOK_COM_SAFE_READY_STATUS
    assert row["rks_gate"] == "RKS_NOT_REQUIRED"
    assert row["blockers"] == ""
    assert safe_evidence_path in row["evidence_paths"]


def test_build_payload_keeps_12_13_blocked_without_outlook_safe_evidence(tmp_path: Path) -> None:
    module = load_module()
    sources = base_sources(tmp_path)
    write_json(
        sources["status_snapshot"],
        {
            "scenarios": [
                {
                    "scenario": "12/13",
                    "current_status": "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
                    "source": str(tmp_path / "s12_13.md"),
                    "source_exists": True,
                }
            ]
        },
    )
    write_json(
        sources["sample_data_map"],
        {
            "rows": [
                {
                    "scenario": "12/13",
                    "sample_data_status": "OUTLOOK_COM_HOLD_SAMPLE_REFRESH_REQUIRED",
                    "artifact_paths": str(tmp_path / "old_sample_hold.md"),
                }
            ]
        },
    )
    write_json(
        sources["safe_execution_map"],
        {
            "rows": [
                {
                    "scenario": "12/13",
                    "safe_suite_status": "NOT_IN_SAFE_SUITE_OUTLOOK_COM_HOLD",
                    "stdout_paths": str(tmp_path / "old_safe_hold.md"),
                }
            ]
        },
    )
    write_json(
        sources["rks_matrix"],
        {
            "rows": [
                {
                    "scenario": "12/13",
                    "current_rks_status": "N_A_NO_PRIMARY_RKS",
                    "runtime_intake_status": "N_A_NO_PRIMARY_RKS",
                }
            ]
        },
    )
    write_json(
        sources["bundle_evidence_validation"],
        {
            "checks": [
                {
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "scenarios": "12/13",
                    "final_evidence_ready": False,
                    "final_evidence_path": "",
                }
            ]
        },
    )

    payload = module.build_payload(sources)

    assert payload["migration_ready_count"] == 0
    row = payload["rows"][0]
    assert row["migration_ready"] is False
    assert "SAMPLE_OR_DRYRUN_EVIDENCE_NOT_READY" in row["blockers"]
    assert "SAFE_EXECUTION_EVIDENCE_NOT_READY" in row["blockers"]


def test_build_markdown_lists_readiness_matrix(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(base_sources(tmp_path))

    markdown = module.build_markdown(payload)

    assert "# 本番移行OK判定ゲート 2026-06-20" in markdown
    assert "prod_migration_ok" in markdown
    assert "43" in markdown
    assert "57" in markdown
    assert "最終実行完了ではない" in markdown


def test_build_ready_candidate_rows_marks_safe_scope(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(base_sources(tmp_path))

    rows = module.build_ready_candidate_rows(payload)

    assert [row["scenario"] for row in rows] == ["43"]
    assert rows[0]["safe_scope"] == "safe dry-run/no-mail/no-submit/no-print/no-payment only"
    assert rows[0]["no_irreversible_operations"] == "YES"


def test_build_blocker_rows_keeps_next_required_action(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(base_sources(tmp_path))

    rows = module.build_blocker_rows(payload)

    assert [row["scenario"] for row in rows] == ["57"]
    assert rows[0]["required_before_migration"] == "rerun safe-stop"
    assert "RKS_GATE_NOT_READY" in rows[0]["blockers"]


def test_build_disposition_rows_separates_safe_candidate_from_hold(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(base_sources(tmp_path))

    rows = module.build_disposition_rows(payload)
    indexed = {row["scenario"]: row for row in rows}

    assert indexed["43"]["kit_inclusion_status"] == "INCLUDE_AS_SAFE_SCOPE_CANDIDATE"
    assert indexed["43"]["executable_in_customer_kit"] == "YES_WITH_SAFE_SCOPE_ONLY"
    assert indexed["43"]["allowed_scope"] == "safe dry-run/no-mail/no-submit/no-print/no-payment only"
    assert indexed["57"]["kit_inclusion_status"] == "INCLUDE_AS_HOLD_OR_REVIEW_ONLY"
    assert indexed["57"]["executable_in_customer_kit"] == "NO"
    assert indexed["57"]["allowed_scope"] == "review/repair/evidence collection only"
    assert "payment execute" in indexed["57"]["prohibited_operations"]


def test_write_csv_uses_expected_fieldnames(tmp_path: Path) -> None:
    module = load_module()
    csv_path = tmp_path / "ready.csv"
    rows = [
        {
            "scenario": "43",
            "migration_ready": True,
            "safe_scope": "safe dry-run/no-mail/no-submit/no-print/no-payment only",
            "current_status": "SCOPED_CONFIRMED_AFTER_FEEDBACK",
            "sample_gate": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
            "safe_execution_gate": "SAFE_SUITE_EXIT0_STDERR0",
            "rks_gate": "RKS_NOT_REQUIRED",
            "cost_scope": "NOT_SUMMARIZED_IN_THIS_COST_MAP",
            "no_irreversible_operations": "YES",
            "next_action": "final click remains human",
            "source": str(tmp_path / "s43.md"),
            "evidence_paths": str(tmp_path / "s43.stdout.txt"),
            "ignored_extra": "not exported",
        }
    ]

    module.write_csv(csv_path, rows, module.READY_CANDIDATE_FIELDNAMES)

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        exported_rows = list(reader)
    assert reader.fieldnames == module.READY_CANDIDATE_FIELDNAMES
    assert exported_rows[0]["scenario"] == "43"
    assert "ignored_extra" not in exported_rows[0]
