import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "generate_safe_execution_evidence_map_20260620.py"
    spec = importlib.util.spec_from_file_location(
        "generate_safe_execution_evidence_map_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_results(tmp_path: Path, results: list[dict]) -> Path:
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps({"results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results_path


def write_outlook_collect_json(tmp_path: Path, ready: bool) -> Path:
    collect_path = tmp_path / "outlook_bundle_evidence_collect.json"
    payload = (
        {
            "status": "READY_FOR_FINAL_EVIDENCE_INTAKE",
            "ready_for_intake": True,
            "log_status": {
                "check_exit": "0",
                "scan_exit": "0",
                "scan_log_path": str(tmp_path / "scan.log"),
            },
        }
        if ready
        else {}
    )
    collect_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return collect_path


def test_build_rows_aggregates_51_and_52_as_one_scenario(tmp_path: Path) -> None:
    module = load_module()
    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stdout.write_text("ok", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    results_path = write_results(
        tmp_path,
        [
            {
                "name": "s51_local_dryrun_skip_download",
                "scenario": "51",
                "status": "EXITED",
                "exit_code": 0,
                "elapsed_sec": 1,
                "safety": "LOCAL dry-run",
                "stdout": str(stdout),
                "stderr": str(stderr),
            },
            {
                "name": "s52_local_dryrun_no_submit",
                "scenario": "52",
                "status": "EXITED",
                "exit_code": 0,
                "elapsed_sec": 1,
                "safety": "LOCAL dry-run/no-submit",
                "stdout": str(stdout),
                "stderr": str(stderr),
            },
        ],
    )

    rows = module.build_rows(results_path)
    row_by_scenario = {row.scenario: row for row in rows}

    assert row_by_scenario["51/52"].safe_suite_status == "SAFE_SUITE_EXIT0_STDERR0"
    assert row_by_scenario["51/52"].task_count == 2
    assert row_by_scenario["51/52"].passed_task_count == 2


def test_build_rows_marks_stderr_output_as_needs_review(tmp_path: Path) -> None:
    module = load_module()
    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stdout.write_text("ok", encoding="utf-8")
    stderr.write_text("warning", encoding="utf-8")
    results_path = write_results(
        tmp_path,
        [
            {
                "name": "s55_matsujitsu_local_dryrun",
                "scenario": "55",
                "status": "EXITED",
                "exit_code": 0,
                "elapsed_sec": 1,
                "safety": "LOCAL dry-run/no-mail",
                "stdout": str(stdout),
                "stderr": str(stderr),
            }
        ],
    )

    rows = module.build_rows(results_path)
    row_by_scenario = {row.scenario: row for row in rows}

    assert row_by_scenario["55"].safe_suite_status == "SAFE_SUITE_NEEDS_REVIEW"
    assert row_by_scenario["55"].passed_task_count == 0
    assert row_by_scenario["55"].production_ready is False


def test_build_payload_keeps_12_13_separate_from_safe_suite(tmp_path: Path) -> None:
    module = load_module()
    module.OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = write_outlook_collect_json(tmp_path, ready=False)
    results_path = write_results(tmp_path, [])

    payload = module.build_payload(results_path)
    rows = payload["rows"]
    assert isinstance(rows, list)
    row_by_scenario = {row["scenario"]: row for row in rows}

    assert row_by_scenario["12/13"]["safe_suite_status"] == "NOT_IN_SAFE_SUITE_OUTLOOK_COM_HOLD"
    assert payload["production_ready_count"] == 0


def test_build_payload_uses_outlook_collect_as_12_13_safe_ready(tmp_path: Path) -> None:
    module = load_module()
    module.OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = write_outlook_collect_json(tmp_path, ready=True)
    results_path = write_results(tmp_path, [])

    payload = module.build_payload(results_path)
    rows = payload["rows"]
    assert isinstance(rows, list)
    row_by_scenario = {row["scenario"]: row for row in rows}

    assert row_by_scenario["12/13"]["safe_suite_status"] == "OUTLOOK_COM_BUNDLE_DRYRUN_NO_PRINT_NO_MAIL_EXIT0"
    assert row_by_scenario["12/13"]["passed_task_count"] == 1
    assert payload["safe_suite_passed_scenario_count"] == 1
    assert payload["missing_or_separate_scenario_count"] == 14
    assert payload["production_ready_count"] == 0


def test_build_markdown_includes_safe_scope_warning() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "safety": "read-only",
        "source_results": "results.json",
        "source_summary": "summary.tsv.numbered",
        "source_audit": "audit.txt.numbered",
        "scenario_count": 1,
        "safe_suite_passed_scenario_count": 1,
        "missing_or_separate_scenario_count": 0,
        "needs_review_scenario_count": 0,
        "production_ready_count": 0,
        "rows": [
            {
                "scenario": "55",
                "safe_suite_status": "SAFE_SUITE_EXIT0_STDERR0",
                "task_count": 1,
                "passed_task_count": 1,
                "stderr_zero_count": 1,
                "task_names": "s55_matsujitsu_local_dryrun",
                "safety_scopes": "LOCAL dry-run/no-mail",
                "stdout_paths": "stdout.txt",
                "stderr_paths": "stderr.txt",
                "evidence_strength": "SAFE_SAMPLE_OR_DRYRUN_EVIDENCE",
                "production_ready": False,
                "remaining_gap": "irreversible operations remain separate gates",
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "does not prove production execution" in markdown
    assert "SAFE_SUITE_EXIT0_STDERR0" in markdown
