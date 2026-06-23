import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_remaining_operator_final_review_pack_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_remaining_operator_final_review_pack_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_payload_uses_active_validation_rows_only(tmp_path: Path) -> None:
    module = load_module()
    latest_evidence = tmp_path / "latest.txt"
    latest_evidence.write_text("ok", encoding="utf-8")
    validation_json = tmp_path / "validation.json"
    remaining_input_csv = tmp_path / "remaining_operator_input.csv"
    input_packet_json = tmp_path / "remaining_operator_input_packet.json"
    remaining_input_csv.write_text("bundle,scenario\nB,44\n", encoding="utf-8")
    validation_json.write_text(
        json.dumps(
            {
                "raw_row_count": 2,
                "scope_exclusion_count": 1,
                "excluded_row_count": 1,
                "rows": [
                    {
                        "bundle": "BUSINESS_REVIEW_BUNDLE",
                        "scenario": "44",
                        "status": "NOT_READY",
                        "blockers": (
                            "MISSING_OPERATOR_FIELDS:"
                            "operator_result,reviewer,reviewed_at"
                        ),
                        "evidence_path": str(tmp_path),
                        "latest_evidence_file": str(latest_evidence),
                        "source_packet_csv": str(tmp_path / "packet.csv"),
                        "source_unified_input_csv": str(tmp_path / "unified.csv"),
                    }
                ],
                "excluded_rows": [
                    {
                        "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                        "scenario": "43",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    input_packet_json.write_text(
        json.dumps(
            {
                "raw_row_count": 2,
                "scope_excluded_row_count": 1,
                "scope_excluded_scenarios": ["43"],
            }
        ),
        encoding="utf-8",
    )

    payload = module.build_payload(validation_json, remaining_input_csv, input_packet_json)

    assert payload["row_count"] == 1
    assert payload["raw_row_count"] == 2
    assert payload["scope_exclusion_count"] == 1
    assert payload["excluded_row_count"] == 1
    assert payload["input_packet_json_exists"] is True
    assert payload["packet_raw_row_count"] == 2
    assert payload["packet_scope_excluded_row_count"] == 1
    assert payload["packet_scope_excluded_scenarios"] == ["43"]
    assert payload["latest_evidence_file_exists_count"] == 1
    assert payload["rows"][0]["scenario"] == "44"
    assert "operator_result" in payload["rows"][0]["next_action"]


def test_write_outputs_creates_review_artifacts(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-23T10:30:00",
        "validation_json": str(tmp_path / "validation.json"),
        "remaining_input_csv": str(tmp_path / "remaining.csv"),
        "input_packet_json": str(tmp_path / "packet.json"),
        "input_packet_json_exists": True,
        "safety": "human review aid only",
        "row_count": 1,
        "not_ready_row_count": 1,
        "evidence_path_exists_count": 1,
        "latest_evidence_file_exists_count": 1,
        "raw_row_count": 2,
        "scope_exclusion_count": 1,
        "excluded_row_count": 1,
        "packet_raw_row_count": 2,
        "packet_scope_excluded_row_count": 1,
        "packet_scope_excluded_scenarios": ["43"],
        "source_scope": "active rows",
        "rows": [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "status": "NOT_READY",
                "blockers": "MISSING_OPERATOR_FIELDS:operator_result",
                "evidence_path": str(tmp_path),
                "latest_evidence_file": str(tmp_path / "latest.txt"),
                "source_packet_csv": str(tmp_path / "packet.csv"),
                "source_unified_input_csv": str(tmp_path / "unified.csv"),
                "next_action": "review",
            }
        ],
    }

    module.write_outputs(payload, tmp_path / "out")

    assert (tmp_path / "out" / "operator_final_review_pack.json").exists()
    assert (tmp_path / "out" / "operator_final_review_index.csv").exists()
    assert (tmp_path / "out" / "operator_final_review_index.html").exists()
    assert (tmp_path / "out" / "START_HERE_operator_final_review.md").exists()
    assert (tmp_path / "out" / "OPEN_OPERATOR_FINAL_REVIEW_PACK.bat").exists()
    markdown = (tmp_path / "out" / "START_HERE_operator_final_review.md").read_text(
        encoding="utf-8"
    )
    assert "row_count: `1`" in markdown
    assert "scope_exclusion_count: `1`" in markdown
    assert "packet_raw_row_count: `2`" in markdown
    assert "packet_scope_excluded_scenarios: `43`" in markdown
