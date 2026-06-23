import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "validate_goal_execution_packet_scope_exclusions_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "validate_goal_execution_packet_scope_exclusions_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_bundle_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "scenario",
        "bundle",
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
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_scope_exclusion_filters_scenario_43_from_active_packet_counts(
    tmp_path: Path,
) -> None:
    module = load_module()
    evidence_path = tmp_path / "evidence.log"
    evidence_path.write_text("ok", encoding="utf-8")
    write_bundle_csv(
        tmp_path / "business_review_bundle.csv",
        [
            {
                "scenario": "43",
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
            },
            {
                "scenario": "70",
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "operator_result": "OK",
                "evidence_path": str(evidence_path),
                "reviewer": "reviewer",
                "reviewed_at": "2026-06-23T10:00:00",
            },
        ],
    )
    scope_exclusions_json = tmp_path / "scope_exclusions.json"
    scope_exclusions_json.write_text(
        json.dumps(
            {
                "exclusions": [
                    {
                        "scenario": "43",
                        "active": True,
                        "reason": "external fix",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = module.build_payload(
        tmp_path,
        tmp_path / "missing_bundle_sheet.csv",
        scope_exclusions_json,
    )
    attention_rows = module.load_legacy_validator().build_attention_rows(payload)

    assert payload["all_packet_rows_approved"] is True
    assert payload["raw_row_count"] == 2
    assert payload["row_count"] == 1
    assert payload["approved_row_count"] == 1
    assert payload["needs_attention_count"] == 0
    assert payload["excluded_row_count"] == 1
    assert payload["rows"][0]["scenario"] == "70"
    assert payload["excluded_rows"][0]["scenario"] == "43"
    assert [row.scenario for row in attention_rows] == []
