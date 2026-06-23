from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
    module_path = repo_root / "tools" / "generate_rks_gate_matrix_20260620_open_probe_20260622.py"
    spec = importlib.util.spec_from_file_location(
        "generate_rks_gate_matrix_20260620_open_probe_20260622",
        module_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_probe(root: Path, folder: str, payload: dict) -> Path:
    target = root / folder
    target.mkdir(parents=True)
    json_path = target / "rks_editor_open_build_probe.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return json_path


def test_load_editor_open_probe_rows_keeps_safe_open_only(tmp_path: Path) -> None:
    module = load_module()
    good_path = write_probe(
        tmp_path,
        "rks_editor_open_build_probe_20260620_20260622_220001",
        {
            "generated_at": "2026-06-22T22:00:01",
            "rows": [
                {
                    "scenario": "42",
                    "executed": True,
                    "metadata_guard_returncode": 0,
                    "editor_open_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "build_artifact_found": False,
                    "button_run_clicked": False,
                },
                {
                    "scenario": "70",
                    "executed": True,
                    "metadata_guard_returncode": 0,
                    "editor_open_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "build_artifact_found": False,
                    "button_run_clicked": True,
                },
            ],
        },
    )

    rows = module.load_editor_open_probe_rows(tmp_path)

    assert rows["42"]["probe_source"] == str(good_path)
    assert rows["42"]["build_artifact_found"] is False
    assert "70" not in rows


def test_build_payload_marks_editor_open_without_resolving_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("evidence", encoding="utf-8")
    write_probe(
        tmp_path,
        "rks_editor_open_build_probe_20260620_20260622_220002",
        {
            "generated_at": "2026-06-22T22:00:02",
            "rows": [
                {
                    "scenario": "42",
                    "executed": True,
                    "metadata_guard_returncode": 0,
                    "editor_open_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "build_artifact_found": False,
                    "button_run_clicked": False,
                }
            ],
        },
    )
    rows = [
        module.row(
            "42",
            "selected RKS",
            "ENTRY_SELECTION_REQUIRED",
            "registry-confirmed exact production file exists",
            "build/runtime/latest clean log",
            "continue gated checks",
            "ButtonRun",
            str(source),
        )
    ]
    monkeypatch.setattr(module, "build_rows", lambda: rows)
    monkeypatch.setattr(module, "RKS_EDITOR_OPEN_PROBE_REPORTS_ROOT", tmp_path)
    monkeypatch.setattr(module, "RKS_RUNTIME_INTAKE_VALIDATION", tmp_path / "missing.json")

    payload = module.build_payload()
    row = payload["rows"][0]

    assert payload["overall_rks_production_ready"] is False
    assert payload["unresolved_rks_gate_count"] == 1
    assert payload["technical_unresolved_rks_gate_count"] == 1
    assert payload["deferred_rks_gate_count"] == 0
    assert payload["rks_technical_gate_complete"] is False
    assert payload["editor_open_probe_confirmed_count"] == 1
    assert row["editor_open_probe_status"] == "RK10_EDITOR_OPEN_CONFIRMED"
    assert row["editor_open_probe_build_artifact_found"] is False
    assert row["editor_open_probe_button_run_clicked"] is False
    assert row["runtime_intake_status"] == "RUNTIME_INTAKE_VALIDATION_MISSING"
    assert "build/runtime not confirmed" in row["strongest_confirmed_scope"]


def test_markdown_lists_editor_open_probe_scope() -> None:
    module = load_module()
    markdown = module.build_markdown(
        {
            "generated_at": "2026-06-22T22:00:00",
            "overall_rks_production_ready": False,
            "safety": "read-only",
            "row_count": 1,
            "unresolved_rks_gate_count": 1,
            "technical_unresolved_rks_gate_count": 1,
            "deferred_rks_gate_count": 0,
            "rks_technical_gate_complete": False,
            "missing_source_count": 0,
            "supplemental_static_guard_audit": "guard.md",
            "supplemental_static_guard_audit_exists": True,
            "runtime_intake_validation": "runtime.json",
            "runtime_intake_validation_exists": False,
            "runtime_intake_validation_complete": False,
            "editor_open_probe_confirmed_count": 1,
            "rows": [
                {
                    "scenario": "42",
                    "current_rks_status": "ENTRY_SELECTION_REQUIRED",
                    "runtime_intake_status": "RUNTIME_INTAKE_VALIDATION_MISSING",
                    "runtime_intake_approved_count": 0,
                    "runtime_intake_required_count": 0,
                    "editor_open_probe_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "editor_open_probe_source": "probe.json",
                    "editor_open_probe_build_artifact_found": False,
                    "editor_open_probe_button_run_clicked": False,
                    "strongest_confirmed_scope": "open only",
                    "missing_gate": "build/runtime",
                    "next_safe_action": "continue",
                    "source_exists": True,
                    "blocked_operation": "ButtonRun",
                    "existing_evidence_search_result": "not_applicable",
                    "primary_source": "source.md",
                }
            ],
        }
    )

    assert "## RK10 Editor Open Probe Evidence" in markdown
    assert "editor open only" in markdown
    assert "button_run_clicked=False" in markdown
