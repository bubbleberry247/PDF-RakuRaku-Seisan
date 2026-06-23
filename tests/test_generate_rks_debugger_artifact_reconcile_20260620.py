import importlib.util
import json
import sys
import zipfile
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "generate_rks_debugger_artifact_reconcile_20260620.py"
    spec = importlib.util.spec_from_file_location(
        "generate_rks_debugger_artifact_reconcile_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_rks(path: Path, program_text: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Program.cs", ("\ufeff" + program_text).encode("utf-8"))
        archive.writestr("meta", b"m" * 1200)
        archive.writestr("id", b"i" * 1200)
        archive.writestr("rootMeta", b"root")
        archive.writestr("version", b"1")


def write_static_audit(path: Path, rks_path: Path, missing_rks_path: Path) -> None:
    payload = {
        "rows": [
            {
                "scenario": "58",
                "rks_path": str(rks_path),
                "static_guard_status": "OK_CANDIDATE",
            },
            {
                "scenario": "99",
                "rks_path": str(missing_rks_path),
                "static_guard_status": "OK_CANDIDATE",
            },
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_payload_matches_debugger_program_and_build_artifacts(tmp_path: Path) -> None:
    module = load_module()
    rks_path = tmp_path / "58.rks"
    missing_rks_path = tmp_path / "missing.rks"
    program_text = "class Program\r\n{\r\n    static void Main() { System.Console.WriteLine(\"58\"); }\r\n}\r\n"
    write_rks(rks_path, program_text)
    audit_path = tmp_path / "audit.json"
    write_static_audit(audit_path, rks_path, missing_rks_path)
    debugger_temp = tmp_path / "Debugger" / "guid-58" / "Temp"
    artifact_dir = debugger_temp / "obj" / "Debug" / "net8.0-windows"
    artifact_dir.mkdir(parents=True)
    (debugger_temp / "Program.cs").write_text(
        program_text.replace("\r\n", "\n"),
        encoding="utf-8",
    )
    (artifact_dir / "Temp.dll").write_bytes(b"dll")

    payload = module.build_payload(audit_path, tmp_path / "Debugger", tmp_path / "out")

    row_by_scenario = {row["scenario"]: row for row in payload["rows"]}
    assert payload["debugger_program_count"] == 1
    assert payload["debugger_program_matched_row_count"] == 1
    assert payload["build_artifact_matched_row_count"] == 1
    assert payload["operator_auto_approved_count"] == 0
    assert row_by_scenario["58"]["debugger_program_match_count"] == 1
    assert row_by_scenario["58"]["build_artifact_found"] is True
    assert row_by_scenario["58"]["supporting_scope"] == "debugger_program_match, build_artifact_present"
    assert row_by_scenario["58"]["operator_auto_approval"] == "NO"
    assert row_by_scenario["99"]["rks_program_found"] is False


def test_write_outputs_creates_json_csv_markdown_numbered(tmp_path: Path) -> None:
    module = load_module()
    rks_path = tmp_path / "58.rks"
    write_rks(rks_path, "class Program { }")
    audit_path = tmp_path / "audit.json"
    write_static_audit(audit_path, rks_path, tmp_path / "missing.rks")
    payload = module.build_payload(audit_path, tmp_path / "Debugger", tmp_path / "out")

    module.write_outputs(payload, tmp_path / "out")

    assert (tmp_path / "out" / "rks_debugger_artifact_reconcile.json").exists()
    assert (tmp_path / "out" / "rks_debugger_artifact_reconcile.csv").exists()
    md_path = tmp_path / "out" / "rks_debugger_artifact_reconcile.md"
    assert md_path.exists()
    assert Path(str(md_path) + ".numbered").exists()
    markdown = md_path.read_text(encoding="utf-8")
    assert "operator_auto_approval" in markdown
    assert "常に `NO`" in markdown
