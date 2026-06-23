import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_minimum_operator_review_input_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_minimum_operator_review_input_20260623",
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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_payload_uses_current_remaining_input_and_preserves_human_fields(
    tmp_path: Path,
) -> None:
    module = load_module()
    latest_44 = tmp_path / "scenario_44_latest.txt"
    latest_44.write_text(
        "\n".join(
            [
                "py_compile_exit=0",
                "verify_message: OK: ready_at=2026-06-23T14:37:08+09:00",
                "submitted: False",
                "UNCONFIRMED missing evidence: RK10 editor open",
            ]
        ),
        encoding="utf-8",
    )
    latest_55 = tmp_path / "scenario_55_latest.txt"
    latest_55.write_text("safe", encoding="utf-8")
    remaining_input_csv = tmp_path / "remaining_operator_input.csv"
    final_review_json = tmp_path / "operator_final_review_pack.json"
    input_packet_json = tmp_path / "remaining_operator_input_packet.json"
    existing_minimum_csv = tmp_path / "minimum_operator_review_input.csv"

    write_csv(
        remaining_input_csv,
        [
            "bundle",
            "scenario",
            "operator_result",
            "reviewer",
            "reviewed_at",
            "latest_evidence_file",
            "source_packet_csv",
            "source_unified_input_csv",
            "allowed_operator_result_values",
            "human_or_external_input_needed",
            "attention_terms",
        ],
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "latest_evidence_file": str(latest_44),
                "source_packet_csv": str(tmp_path / "packet_44.csv"),
                "source_unified_input_csv": str(tmp_path / "unified.csv"),
                "allowed_operator_result_values": "OK / NG / HOLD",
                "human_or_external_input_needed": "business review",
                "attention_terms": "review",
            },
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "55",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "latest_evidence_file": str(latest_55),
                "source_packet_csv": str(tmp_path / "packet_55.csv"),
                "source_unified_input_csv": str(tmp_path / "unified.csv"),
                "allowed_operator_result_values": "OK / NG / HOLD",
                "human_or_external_input_needed": "",
                "attention_terms": "",
            },
        ],
    )
    write_csv(
        existing_minimum_csv,
        [
            "bundle",
            "scenario",
            "operator_result",
            "reviewer",
            "reviewed_at",
        ],
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "HOLD",
                "reviewer": "reviewer-a",
                "reviewed_at": "2026-06-23T14:00:00",
            }
        ],
    )
    final_review_json.write_text(
        json.dumps(
            {
                "scope_exclusion_count": 1,
                "packet_raw_row_count": 11,
                "packet_scope_excluded_row_count": 1,
                "packet_scope_excluded_scenarios": ["43"],
                "rows": [
                    {
                        "bundle": "BUSINESS_REVIEW_BUNDLE",
                        "scenario": "44",
                        "status": "NOT_READY",
                        "blockers": "MISSING_OPERATOR_FIELDS",
                        "latest_evidence_file": str(tmp_path / "stale.txt"),
                    },
                    {
                        "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                        "scenario": "55",
                        "status": "NOT_READY",
                        "blockers": "MISSING_OPERATOR_FIELDS",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    input_packet_json.write_text(
        json.dumps(
            {
                "raw_row_count": 11,
                "scope_excluded_row_count": 1,
                "scope_excluded_scenarios": ["43"],
            }
        ),
        encoding="utf-8",
    )

    payload = module.build_payload(
        remaining_input_csv,
        final_review_json,
        input_packet_json,
        existing_minimum_csv,
    )

    assert payload["row_count"] == 2
    assert payload["scope_exclusion_count"] == 1
    assert payload["packet_scope_excluded_scenarios"] == ["43"]
    assert payload["operator_fields_preserved_from_existing_minimum_csv"] == 3
    assert payload["complete_operator_row_count"] == 1
    assert payload["blank_operator_row_count"] == 1
    assert "43" not in [row["scenario"] for row in payload["rows"]]
    row_44 = payload["rows"][0]
    assert row_44["scenario"] == "44"
    assert row_44["operator_result"] == "HOLD"
    assert row_44["reviewer"] == "reviewer-a"
    assert row_44["latest_evidence_file"] == str(latest_44)
    assert "py_compile_exit=0" in row_44["evidence_success_signals"]
    assert "UNCONFIRMED" in row_44["evidence_attention_signals"]
    assert "submitted: False" in row_44["evidence_safety_signals"]
    row_55 = payload["rows"][1]
    assert row_55["operator_result"] == ""
    assert row_55["reviewer"] == ""
    assert row_55["reviewed_at"] == ""
    assert row_55["evidence_success_signals"] == ""


def test_write_outputs_creates_minimum_review_artifacts(tmp_path: Path) -> None:
    module = load_module()
    latest_evidence = tmp_path / "scenario_44_latest.txt"
    latest_evidence.write_text("safe", encoding="utf-8")
    payload = {
        "generated_at": "2026-06-23T14:30:00",
        "safety": "manual input aid plus optional Codex auto-evidence fill",
        "remaining_input_csv": str(tmp_path / "remaining.csv"),
        "remaining_input_csv_exists": True,
        "final_review_json": str(tmp_path / "final.json"),
        "final_review_json_exists": True,
        "input_packet_json": str(tmp_path / "packet.json"),
        "input_packet_json_exists": True,
        "existing_minimum_csv": str(tmp_path / "minimum.csv"),
        "existing_minimum_csv_exists": True,
        "row_count": 1,
        "complete_operator_row_count": 0,
        "blank_operator_row_count": 1,
        "partial_operator_row_count": 0,
        "source_operator_field_count": 0,
        "operator_fields_preserved_from_existing_minimum_csv": 0,
        "latest_evidence_file_exists_count": 1,
        "scope_exclusion_count": 1,
        "packet_raw_row_count": 2,
        "packet_scope_excluded_row_count": 1,
        "packet_scope_excluded_scenarios": ["43"],
        "minimum_input_csv": str(tmp_path / "out" / "minimum_operator_review_input.csv"),
        "html_input_ui": str(tmp_path / "out" / "minimum_operator_review_input.html"),
        "open_ui_bat": str(tmp_path / "out" / "OPEN_minimum_operator_review_input.bat"),
        "guided_fill_ps1": str(
            tmp_path / "out" / "GUIDED_FILL_minimum_operator_review_input.ps1"
        ),
        "guided_fill_bat": str(
            tmp_path / "out" / "GUIDED_FILL_minimum_operator_review_input.bat"
        ),
        "auto_fill_and_apply_bat": str(
            tmp_path
            / "out"
            / "AUTO_FILL_AND_APPLY_FROM_CODEX_EVIDENCE_minimum_operator_review_input.bat"
        ),
        "apply_bat": str(
            tmp_path / "out" / "APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat"
        ),
        "apply_script": str(tmp_path / "out" / "apply_minimum_operator_review_input.py"),
        "apply_script_exists": True,
        "rows": [
            {
                "row_number": 1,
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "allowed_operator_result": "OK / NG / HOLD",
                "latest_evidence_file": str(latest_evidence),
                "latest_evidence_exists": "YES",
                "latest_evidence_uri": latest_evidence.absolute().as_uri(),
                "evidence_path": str(tmp_path),
                "source_remaining_operator_input_csv": str(tmp_path / "remaining.csv"),
                "source_packet_csv": str(tmp_path / "packet.csv"),
                "source_unified_input_csv": str(tmp_path / "unified.csv"),
                "status": "NOT_READY",
                "blockers": "MISSING_OPERATOR_FIELDS",
                "human_or_external_input_needed": "business review",
                "attention_terms": "review",
            }
        ],
    }

    module.write_outputs(payload, tmp_path / "out")

    assert (tmp_path / "out" / "minimum_operator_review_pack.json").exists()
    assert (tmp_path / "out" / "minimum_operator_review_input.csv").exists()
    assert (tmp_path / "out" / "minimum_operator_review_input.html").exists()
    assert (tmp_path / "out" / "minimum_operator_review_input_summary.md").exists()
    assert (tmp_path / "out" / "START_HERE_minimum_operator_review.md").exists()
    assert (tmp_path / "out" / "OPEN_minimum_operator_review_input.bat").exists()
    assert (
        tmp_path / "out" / "APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat"
    ).exists()
    assert (tmp_path / "out" / "GUIDED_FILL_minimum_operator_review_input.ps1").exists()
    assert (tmp_path / "out" / "GUIDED_FILL_minimum_operator_review_input.bat").exists()
    assert (
        tmp_path
        / "out"
        / "AUTO_FILL_AND_APPLY_FROM_CODEX_EVIDENCE_minimum_operator_review_input.bat"
    ).exists()
    assert (
        tmp_path / "out" / "minimum_operator_review_input_summary.md.numbered"
    ).exists()
    summary = (tmp_path / "out" / "minimum_operator_review_input_summary.md").read_text(
        encoding="utf-8"
    )
    html = (tmp_path / "out" / "minimum_operator_review_input.html").read_text(
        encoding="utf-8"
    )
    open_bat = (tmp_path / "out" / "OPEN_minimum_operator_review_input.bat").read_text(
        encoding="ascii"
    )
    guided_bat = (
        tmp_path / "out" / "GUIDED_FILL_minimum_operator_review_input.bat"
    ).read_text(encoding="ascii")
    guided_ps1 = (
        tmp_path / "out" / "GUIDED_FILL_minimum_operator_review_input.ps1"
    ).read_text(encoding="utf-8-sig")
    apply_bat = (
        tmp_path / "out" / "APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat"
    ).read_text(encoding="ascii")
    auto_fill_bat = (
        tmp_path
        / "out"
        / "AUTO_FILL_AND_APPLY_FROM_CODEX_EVIDENCE_minimum_operator_review_input.bat"
    ).read_text(encoding="ascii")
    with (tmp_path / "out" / "minimum_operator_review_input.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert "scope_exclusion_count: `1`" in summary
    assert "packet_scope_excluded_scenarios: `43`" in summary
    assert "Codex自動確認" in summary
    assert "GUIDED_FILL_minimum_operator_review_input.bat" in (
        tmp_path / "out" / "START_HERE_minimum_operator_review.md"
    ).read_text(encoding="utf-8")
    assert "scenario_44_latest.txt" in html
    assert str(module.ROOT) not in open_bat
    assert str(module.ROOT) not in apply_bat
    assert str(module.ROOT) not in guided_bat
    assert str(module.ROOT) not in auto_fill_bat
    assert "Read-Host 'Reviewer name (required)'" in guided_ps1
    assert "Enter exactly OK, NG, or HOLD" in guided_ps1
    assert "does not auto-approve" in guided_ps1
    assert 'operator_result = "OK"' not in guided_ps1
    assert 'set "PACK_DIR=%~dp0"' in open_bat
    assert 'set "PACK_DIR=%~dp0"' in guided_bat
    assert 'set "PACK_DIR=%~dp0"' in auto_fill_bat
    assert "auto_fill_minimum_operator_review_input_20260623.py" in auto_fill_bat
    assert 'set "TOOLS_RUNNER=%ROOT_DIR%\\tools\\run_safe_goal_checks_20260620_ai_default_probe_20260622.py"' in apply_bat
    assert "review/input only" in apply_bat
    assert rows[0]["scenario"] == "44"
    assert rows[0]["operator_result"] == ""
