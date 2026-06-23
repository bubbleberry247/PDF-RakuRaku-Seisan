import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_remaining_operator_input_packet_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_remaining_operator_input_packet_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_payload_keeps_only_unapproved_rows_and_blank_operator_fields(
    tmp_path: Path,
) -> None:
    module = load_module()
    packet_csv = tmp_path / "business_review_bundle.csv"
    execution_json = tmp_path / "execution_validation.json"
    fill_queue_json = tmp_path / "fill_queue.json"
    unified_csv = tmp_path / "unified.csv"
    write_csv(
        packet_csv,
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "current_safe_evidence": r"C:\safe\s44.md.numbered",
                "current_safe_evidence_scope": "reference_only_not_operator_approval",
            },
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "12/13",
                "current_safe_evidence": r"C:\safe\s12.md.numbered",
                "current_safe_evidence_scope": "reference_only_not_operator_approval",
            },
        ],
    )
    write_json(
        execution_json,
        {
            "rows": [
                {
                    "csv_path": str(packet_csv),
                    "scenario": "44",
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "operator_result": "",
                    "evidence_path": str(tmp_path / "evidence" / "scenario_44"),
                    "reviewer": "",
                    "reviewed_at": "",
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result, reviewer, reviewed_at",
                    "evidence_exists": True,
                    "approved": False,
                },
                {
                    "csv_path": str(packet_csv),
                    "scenario": "12/13",
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "operator_result": "OK",
                    "evidence_path": str(tmp_path / "evidence" / "scenario_12_13"),
                    "reviewer": "codex",
                    "reviewed_at": "2026-06-22T20:27:00",
                    "status": "APPROVED_WITH_EVIDENCE",
                    "missing_fields": "",
                    "evidence_exists": True,
                    "approved": True,
                },
            ]
        },
    )
    write_json(
        fill_queue_json,
        {
            "rows": [
                {
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "start_here_path": str(tmp_path / "business_review_START_HERE.md"),
                    "forbidden": "review未了のままRakuraku登録",
                    "after_action_command": "python fixed_runner.py",
                }
            ]
        },
    )

    payload = module.build_payload(
        execution_json,
        fill_queue_json,
        unified_csv,
        existing_input_csv=tmp_path / "missing_existing_input.csv",
        evidence_digest_json=tmp_path / "missing_digest.json",
    )

    assert payload["row_count"] == 1
    assert payload["operator_fields_prefilled"] == 0
    assert payload["operator_fields_preserved_from_existing_csv"] == 0
    assert payload["after_fill_bat_name"] == "RUN_AFTER_FILL_remaining_operator_input.bat"
    assert payload["open_review_bat_name"] == "OPEN_REVIEW_remaining_operator_evidence.bat"
    assert payload["start_here_name"] == "START_HERE_remaining_operator_input.md"
    assert "validate_remaining_operator_input_ready_20260623.py" in payload[
        "after_fill_precheck_command"
    ]
    assert "run_safe_goal_checks_20260620_ai_default_probe_20260622.py" in payload[
        "after_fill_command"
    ]
    assert "RPA開発版AI付き" in payload["license_policy"]
    row = payload["rows"][0]
    assert row["bundle"] == "BUSINESS_REVIEW_BUNDLE"
    assert row["scenario"] == "44"
    assert row["operator_result"] == ""
    assert row["reviewer"] == ""
    assert row["reviewed_at"] == ""
    assert row["current_safe_evidence"] == r"C:\safe\s44.md.numbered"
    assert row["current_safe_evidence_scope"] == "reference_only_not_operator_approval"
    assert row["latest_evidence_file"] == ""
    assert row["attention_terms"] == ""
    assert row["human_or_external_input_needed"] == ""
    assert row["source_unified_input_csv"] == str(unified_csv)
    assert row["hard_stop"] == "review未了のままRakuraku登録"


def test_build_payload_adds_digest_fields_when_available(tmp_path: Path) -> None:
    module = load_module()
    packet_csv = tmp_path / "rk10_editor_runtime_bundle.csv"
    execution_json = tmp_path / "execution_validation.json"
    fill_queue_json = tmp_path / "fill_queue.json"
    unified_csv = tmp_path / "unified.csv"
    digest_json = tmp_path / "remaining_operator_evidence_digest.json"
    write_csv(
        packet_csv,
        [
            {
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "scenario": "56",
                "current_safe_evidence": r"C:\safe\s56.md.numbered",
                "current_safe_evidence_scope": "reference_only_not_operator_approval",
            }
        ],
    )
    write_json(
        execution_json,
        {
            "rows": [
                {
                    "csv_path": str(packet_csv),
                    "scenario": "56",
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "operator_result": "",
                    "evidence_path": str(tmp_path / "evidence" / "scenario_56"),
                    "reviewer": "",
                    "reviewed_at": "",
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result, reviewer, reviewed_at",
                    "evidence_exists": True,
                    "approved": False,
                }
            ]
        },
    )
    write_json(fill_queue_json, {"rows": []})
    write_json(
        digest_json,
        {
            "rows": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenario": "56",
                    "latest_evidence_file": r"C:\evidence\s56.txt",
                    "attention_terms": "NG_META_MISSING",
                    "human_or_external_input_needed": "RKS要否判断",
                }
            ]
        },
    )

    payload = module.build_payload(
        execution_json,
        fill_queue_json,
        unified_csv,
        existing_input_csv=tmp_path / "missing_existing_input.csv",
        evidence_digest_json=digest_json,
    )

    row = payload["rows"][0]
    assert payload["source_evidence_digest_exists"] is True
    assert row["latest_evidence_file"] == r"C:\evidence\s56.txt"
    assert row["attention_terms"] == "NG_META_MISSING"
    assert row["human_or_external_input_needed"] == "RKS要否判断"


def test_build_payload_excludes_scope_excluded_rows(tmp_path: Path) -> None:
    module = load_module()
    packet_csv = tmp_path / "business_data_approval_bundle.csv"
    execution_json = tmp_path / "execution_validation.json"
    fill_queue_json = tmp_path / "fill_queue.json"
    unified_csv = tmp_path / "unified.csv"
    scope_exclusions_json = tmp_path / "scope_exclusions.json"
    write_csv(
        packet_csv,
        [
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "43",
                "current_safe_evidence": r"C:\safe\s43.md.numbered",
                "current_safe_evidence_scope": "excluded_by_user",
            },
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "current_safe_evidence": r"C:\safe\s44.md.numbered",
                "current_safe_evidence_scope": "reference_only_not_operator_approval",
            },
        ],
    )
    write_json(
        execution_json,
        {
            "rows": [
                {
                    "csv_path": str(packet_csv),
                    "scenario": "43",
                    "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                    "operator_result": "",
                    "evidence_path": str(tmp_path / "evidence" / "scenario_43"),
                    "reviewer": "",
                    "reviewed_at": "",
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result, reviewer, reviewed_at",
                    "evidence_exists": True,
                    "approved": False,
                },
                {
                    "csv_path": str(packet_csv),
                    "scenario": "44",
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "operator_result": "",
                    "evidence_path": str(tmp_path / "evidence" / "scenario_44"),
                    "reviewer": "",
                    "reviewed_at": "",
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result, reviewer, reviewed_at",
                    "evidence_exists": True,
                    "approved": False,
                },
            ]
        },
    )
    write_json(fill_queue_json, {"rows": []})
    write_json(
        scope_exclusions_json,
        {"exclusions": [{"scenario": "43", "active": True}]},
    )

    payload = module.build_payload(
        execution_json,
        fill_queue_json,
        unified_csv,
        existing_input_csv=tmp_path / "missing_existing_input.csv",
        evidence_digest_json=tmp_path / "missing_digest.json",
        scope_exclusions_json=scope_exclusions_json,
    )

    assert payload["raw_row_count"] == 2
    assert payload["row_count"] == 1
    assert payload["scope_excluded_row_count"] == 1
    assert payload["scope_excluded_scenarios"] == ["43"]
    assert payload["rows"][0]["scenario"] == "44"


def test_build_payload_preserves_existing_operator_fields(tmp_path: Path) -> None:
    module = load_module()
    packet_csv = tmp_path / "business_data_approval_bundle.csv"
    execution_json = tmp_path / "execution_validation.json"
    fill_queue_json = tmp_path / "fill_queue.json"
    unified_csv = tmp_path / "unified.csv"
    existing_input_csv = tmp_path / "remaining_operator_input.csv"
    write_csv(
        packet_csv,
        [
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "55",
                "current_safe_evidence": r"C:\safe\s55.md.numbered",
                "current_safe_evidence_scope": "reference_only_not_operator_approval",
            }
        ],
    )
    write_csv(
        existing_input_csv,
        [
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "55",
                "operator_result": "OK",
                "reviewer": "operator_a",
                "reviewed_at": "2026-06-23T05:15:00",
            }
        ],
    )
    write_json(
        execution_json,
        {
            "rows": [
                {
                    "csv_path": str(packet_csv),
                    "scenario": "55",
                    "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                    "operator_result": "",
                    "evidence_path": str(tmp_path / "evidence" / "scenario_55"),
                    "reviewer": "",
                    "reviewed_at": "",
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result, reviewer, reviewed_at",
                    "evidence_exists": True,
                    "approved": False,
                }
            ]
        },
    )
    write_json(fill_queue_json, {"rows": []})

    payload = module.build_payload(
        execution_json,
        fill_queue_json,
        unified_csv,
        existing_input_csv=existing_input_csv,
        evidence_digest_json=tmp_path / "missing_digest.json",
    )

    row = payload["rows"][0]
    assert payload["operator_fields_prefilled"] == 0
    assert payload["operator_fields_preserved_from_existing_csv"] == 1
    assert payload["operator_complete_rows_preserved_from_existing_csv"] == 1
    assert row["operator_result"] == "OK"
    assert row["reviewer"] == "operator_a"
    assert row["reviewed_at"] == "2026-06-23T05:15:00"


def test_write_outputs_creates_csv_json_markdown_and_numbered(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-23T05:10:00",
        "safety": "operator aid only",
        "source_execution_validation_json": str(tmp_path / "execution.json"),
        "source_fill_queue_json": str(tmp_path / "fill.json"),
        "source_unified_input_csv": str(tmp_path / "unified.csv"),
        "source_scope_exclusions_json": str(tmp_path / "scope.json"),
        "source_evidence_digest_json": str(tmp_path / "digest.json"),
        "source_evidence_digest_exists": True,
        "source_evidence_digest_markdown": str(tmp_path / "digest.md.numbered"),
        "raw_row_count": 1,
        "scope_excluded_scenarios": [],
        "scope_excluded_row_count": 0,
        "row_count": 1,
        "bundle_count": 1,
        "bundles": ["BUSINESS_REVIEW_BUNDLE"],
        "operator_fields_prefilled": 0,
        "operator_fields_preserved_from_existing_csv": 0,
        "operator_complete_rows_preserved_from_existing_csv": 0,
        "blank_operator_fields": ["operator_result", "reviewer", "reviewed_at"],
        "after_fill_bat_name": "RUN_AFTER_FILL_remaining_operator_input.bat",
        "open_review_bat_name": "OPEN_REVIEW_remaining_operator_evidence.bat",
        "start_here_name": "START_HERE_remaining_operator_input.md",
        "after_fill_precheck_command": (
            r'"C:\Users\masam\AppData\Local\Programs\Python\Python313\python.exe" '
            r'-X utf8 "C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan'
            r'\tools\validate_remaining_operator_input_ready_20260623.py" '
            r"--fail-on-not-ready"
        ),
        "after_fill_command": (
            r'"C:\Users\masam\AppData\Local\Programs\Python\Python313\python.exe" '
            r'-X utf8 "C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan'
            r'\tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py" '
            r"--s12-exit-code 2"
        ),
        "license_policy": (
            "RK10ライセンス画面は既定のRPA開発版AI付きのまま、"
            "ラジオボタンを変更せずOKのみ押す。"
        ),
        "rows": [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "evidence_path": str(tmp_path / "evidence"),
                "evidence_exists": "True",
                "missing_fields": "operator_result, reviewer, reviewed_at",
                "source_packet_csv": str(tmp_path / "packet.csv"),
                "source_unified_input_csv": str(tmp_path / "unified.csv"),
                "start_here_path": str(tmp_path / "START_HERE.md"),
                "current_safe_evidence": str(tmp_path / "safe.md.numbered"),
                "current_safe_evidence_scope": "reference_only_not_operator_approval",
                "latest_evidence_file": str(tmp_path / "latest_evidence.txt"),
                "attention_terms": "NG_META_MISSING",
                "human_or_external_input_needed": "RKS要否判断",
                "allowed_operator_result_values": "OK / NG / HOLD",
                "hard_stop": "review未了",
                "after_action_command": "python fixed_runner.py",
                "copy_instruction": (
                    "Fill only operator_result/reviewer/reviewed_at, then run "
                    "the fixed safe runner."
                ),
            }
        ],
    }

    module.write_outputs(payload, tmp_path / "out")

    assert (tmp_path / "out" / "remaining_operator_input_packet.json").exists()
    assert (tmp_path / "out" / "remaining_operator_input_packet.json.numbered").exists()
    assert (tmp_path / "out" / "remaining_operator_input.csv").exists()
    assert (tmp_path / "out" / "remaining_operator_input.csv.numbered").exists()
    assert (tmp_path / "out" / "START_HERE_remaining_operator_input.md").exists()
    assert (
        tmp_path / "out" / "START_HERE_remaining_operator_input.md.numbered"
    ).exists()
    assert (tmp_path / "out" / "RUN_AFTER_FILL_remaining_operator_input.bat").exists()
    assert (tmp_path / "out" / "OPEN_REVIEW_remaining_operator_evidence.bat").exists()
    markdown = (tmp_path / "out" / "remaining_operator_input_packet.md").read_text(
        encoding="utf-8",
    )
    start_here = (tmp_path / "out" / "START_HERE_remaining_operator_input.md").read_text(
        encoding="utf-8",
    )
    after_fill_bat = (
        tmp_path / "out" / "RUN_AFTER_FILL_remaining_operator_input.bat"
    ).read_text(encoding="ascii")
    open_review_bat = (
        tmp_path / "out" / "OPEN_REVIEW_remaining_operator_evidence.bat"
    ).read_text(encoding="ascii")
    assert "Fill only `operator_result`, `reviewer`, and `reviewed_at`" in markdown
    assert "OPEN_REVIEW_remaining_operator_evidence.bat" in markdown
    assert "NG_META_MISSING" in markdown
    assert "RUN_AFTER_FILL_remaining_operator_input.bat" in markdown
    assert "after_fill_precheck_command" in markdown
    assert "The sync step copies complete stamps" in markdown
    assert "Do not run production registration" in markdown
    assert "RPA開発版AI付き" in start_here
    assert "Review digest" in start_here
    assert "RK10 ButtonRun" in start_here
    assert "validate_remaining_operator_input_ready_20260623.py" in after_fill_bat
    assert "[1/2]" in after_fill_bat
    assert "[2/2]" in after_fill_bat
    assert "PRECHECK_RC" in after_fill_bat
    assert "run_safe_goal_checks_20260620_ai_default_probe_20260622.py" in after_fill_bat
    assert "--s12-exit-code 2" in after_fill_bat
    assert "digest.md.numbered" in open_review_bat
