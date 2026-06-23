import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "generate_sample_data_evidence_map_20260620.py"
    spec = importlib.util.spec_from_file_location(
        "generate_sample_data_evidence_map_20260620",
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


def write_artifacts(tmp_path: Path, stem: str) -> tuple[Path, Path, Path]:
    stdout = tmp_path / f"{stem}.stdout.txt"
    stderr = tmp_path / f"{stem}.stderr.txt"
    meta = tmp_path / f"{stem}.meta.txt"
    stdout.write_text("ok", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    meta.write_text("meta", encoding="utf-8")
    return stdout, stderr, meta


def write_outlook_collect_json(tmp_path: Path, ready: bool, evidence_path: Path | None = None) -> Path:
    collect_path = tmp_path / "outlook_bundle_evidence_collect.json"
    payload = (
        {
            "status": "READY_FOR_FINAL_EVIDENCE_INTAKE",
            "ready_for_intake": True,
            "evidence_path": str(evidence_path or tmp_path),
            "log_status": {
                "check_exit": "0",
                "scan_exit": "0",
            },
        }
        if ready
        else {}
    )
    collect_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return collect_path


def test_build_rows_aggregates_51_and_52_artifacts(tmp_path: Path) -> None:
    module = load_module()
    stdout, stderr, meta = write_artifacts(tmp_path, "task")
    results_path = write_results(
        tmp_path,
        [
            {
                "name": "s51_local_dryrun_skip_download",
                "scenario": "51",
                "status": "EXITED",
                "exit_code": 0,
                "safety": "LOCAL dry-run",
                "working_directory": r"C:\s51",
                "stdout": str(stdout),
                "stderr": str(stderr),
                "meta": str(meta),
            },
            {
                "name": "s52_local_dryrun_no_submit",
                "scenario": "52",
                "status": "EXITED",
                "exit_code": 0,
                "safety": "LOCAL dry-run/no-submit",
                "working_directory": r"C:\s52",
                "stdout": str(stdout),
                "stderr": str(stderr),
                "meta": str(meta),
            },
        ],
    )

    rows = module.build_rows(results_path)
    row_by_scenario = {row.scenario: row for row in rows}

    assert row_by_scenario["51/52"].sample_data_status == "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT"
    assert row_by_scenario["51/52"].task_count == 2
    assert row_by_scenario["51/52"].passed_task_count == 2
    assert row_by_scenario["51/52"].artifact_file_count == 6


def test_build_rows_marks_missing_artifact_as_review(tmp_path: Path) -> None:
    module = load_module()
    stdout, stderr, meta = write_artifacts(tmp_path, "task")
    meta.unlink()
    results_path = write_results(
        tmp_path,
        [
            {
                "name": "s58_sample_generate_verify",
                "scenario": "58",
                "status": "EXITED",
                "exit_code": 0,
                "safety": "sample data generation/verification only",
                "working_directory": r"C:\s58",
                "stdout": str(stdout),
                "stderr": str(stderr),
                "meta": str(meta),
            }
        ],
    )

    rows = module.build_rows(results_path)
    row_by_scenario = {row.scenario: row for row in rows}

    assert row_by_scenario["58"].sample_data_status == "SAFE_SUITE_SAMPLE_ARTIFACTS_NEED_REVIEW"
    assert row_by_scenario["58"].artifact_file_count == 2


def test_build_payload_keeps_12_13_as_separate_hold(tmp_path: Path) -> None:
    module = load_module()
    module.OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = write_outlook_collect_json(tmp_path, ready=False)
    results_path = write_results(tmp_path, [])

    payload = module.build_payload(results_path)
    rows = payload["rows"]
    assert isinstance(rows, list)
    row_by_scenario = {row["scenario"]: row for row in rows}

    assert row_by_scenario["12/13"]["sample_data_status"] == "OUTLOOK_COM_HOLD_SAMPLE_REFRESH_REQUIRED"
    assert payload["separate_hold_count"] == 1
    assert payload["production_ready_count"] == 0


def test_build_payload_uses_outlook_collect_as_12_13_sample_ready(tmp_path: Path) -> None:
    module = load_module()
    evidence_dir = tmp_path / "scenario_12_13"
    evidence_dir.mkdir()
    module.OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = write_outlook_collect_json(
        tmp_path,
        ready=True,
        evidence_path=evidence_dir,
    )
    results_path = write_results(tmp_path, [])

    payload = module.build_payload(results_path)
    rows = payload["rows"]
    assert isinstance(rows, list)
    row_by_scenario = {row["scenario"]: row for row in rows}

    assert row_by_scenario["12/13"]["sample_data_status"] == "OUTLOOK_COM_BUNDLE_DRYRUN_SAMPLE_REFRESH_READY"
    assert row_by_scenario["12/13"]["passed_task_count"] == 1
    assert payload["sample_or_dryrun_artifact_ready_count"] == 1
    assert payload["separate_hold_count"] == 0
    assert payload["production_ready_count"] == 0


def test_build_markdown_includes_production_scope_warning() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "safety": "read-only",
        "source_results": "results.json",
        "source_summary": "summary.tsv.numbered",
        "scenario_count": 1,
        "sample_or_dryrun_artifact_ready_count": 1,
        "separate_hold_count": 0,
        "needs_review_count": 0,
        "production_ready_count": 0,
        "rows": [
            {
                "scenario": "38",
                "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                "task_count": 1,
                "passed_task_count": 1,
                "artifact_file_count": 3,
                "task_names": "s38_create_test_data",
                "safety_scopes": "sample workbook generation",
                "working_directories": r"C:\s38",
                "artifact_paths": r"C:\stdout.txt",
                "evidence_strength": "SAFE_SAMPLE_OR_DRYRUN_ARTIFACT_EVIDENCE",
                "production_ready": False,
                "remaining_gap": "production remains separate",
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "Sample Data Evidence Map" in markdown
    assert "does not prove RK10 production runtime" in markdown
    assert "s38_create_test_data" in markdown
