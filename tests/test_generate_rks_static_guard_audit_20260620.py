import importlib.util
import sys
import zipfile
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "generate_rks_static_guard_audit_20260620.py"
    spec = importlib.util.spec_from_file_location(
        "generate_rks_static_guard_audit_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_rks(path: Path, program: bytes, meta: bytes, item_id: bytes) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Program.cs", program)
        archive.writestr("meta", meta)
        archive.writestr("id", item_id)
        archive.writestr("rootMeta", b"root")
        archive.writestr("version", b"1")


def test_inspect_candidate_records_static_guard_and_unconfirmed_gate(tmp_path: Path) -> None:
    module = load_module()
    rks_path = tmp_path / "ok_candidate.rks"
    write_rks(
        rks_path,
        b"public class Program { }",
        b"m" * 1200,
        b"i" * 1200,
    )
    candidate = module.RksAuditCandidate(
        "99",
        "sample candidate",
        str(rks_path),
        "open-build",
        "",
        "RK10 open/build/runtime/latest clean log",
    )
    inspect_rks = module.load_skill_function("rks_metadata_guard.py", "inspect_rks")
    decide = module.load_skill_function("rks_status_gate.py", "decide")

    row = module.inspect_candidate(candidate, inspect_rks, decide)

    assert row.rks_exists is True
    assert row.static_guard_status == "OK_CANDIDATE"
    assert row.non_gui_status_gate == "UNCONFIRMED"
    assert row.production_ready is False


def test_inspect_candidate_flags_risky_tiny_metadata(tmp_path: Path) -> None:
    module = load_module()
    rks_path = tmp_path / "risky_candidate.rks"
    write_rks(
        rks_path,
        b"x" * 4000,
        b"tiny",
        b"tiny",
    )
    candidate = module.RksAuditCandidate(
        "98",
        "risky candidate",
        str(rks_path),
        "open-build",
        "",
        "regenerate via RK10 Editor Save As",
    )
    inspect_rks = module.load_skill_function("rks_metadata_guard.py", "inspect_rks")
    decide = module.load_skill_function("rks_status_gate.py", "decide")

    row = module.inspect_candidate(candidate, inspect_rks, decide)

    assert row.static_guard_status == "RISK_TINY_META"
    assert row.non_gui_status_gate == "NG"
    assert "static guard failed" in row.non_gui_status_reason


def test_parse_existing_status_gate_reads_numbered_report(tmp_path: Path) -> None:
    module = load_module()
    status_report = tmp_path / "status_gate.md.numbered"
    status_report.write_text(
        "   1: # RK10 RKS Status Gate\n"
        "   5: Final status: `OK_FOR_SAFE_STOP_TEST`\n",
        encoding="utf-8",
    )

    status = module.parse_existing_status_gate(str(status_report))

    assert status == "OK_FOR_SAFE_STOP_TEST"


def test_parse_existing_status_gate_does_not_treat_scenario_id_as_status(tmp_path: Path) -> None:
    module = load_module()
    status_report = tmp_path / "summary.tsv.numbered"
    status_report.write_text(
        "   1: scenario\tguard_rc\teditor_status\n"
        "   2: 57\t0\tRK10_EDITOR_OPEN_CONFIRMED\n",
        encoding="utf-8",
    )

    status = module.parse_existing_status_gate(str(status_report))

    assert status == ""


def test_build_markdown_includes_warning_and_paths(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "safety": "read-only",
        "candidate_count": 1,
        "existing_rks_count": 1,
        "ok_candidate_count": 1,
        "risk_or_missing_count": 0,
        "safe_stop_evidence_count": 0,
        "production_ready_count": 0,
        "overall_production_ready": False,
        "rows": [
            {
                "scenario": "99",
                "label": "sample",
                "rks_path": str(tmp_path / "sample.rks"),
                "rks_exists": True,
                "static_guard_status": "OK_CANDIDATE",
                "file_size": 1,
                "program_cs_bytes": 1,
                "meta_bytes": 1,
                "id_bytes": 1,
                "root_meta_bytes": 1,
                "version_bytes": 1,
                "has_safe_test": False,
                "has_show_alert_dialog": False,
                "compile_risk_patterns": "",
                "non_gui_status_gate": "UNCONFIRMED",
                "non_gui_status_reason": "missing evidence",
                "existing_status_gate_evidence": "",
                "existing_status_gate_exists": False,
                "existing_status_gate_status": "",
                "intended_scope": "open-build",
                "production_ready": False,
                "required_next_gate": "RK10 open/build/runtime",
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "This audit does not prove RK10 Editor open" in markdown
    assert "OK_CANDIDATE" in markdown
    assert str(tmp_path / "sample.rks") in markdown
