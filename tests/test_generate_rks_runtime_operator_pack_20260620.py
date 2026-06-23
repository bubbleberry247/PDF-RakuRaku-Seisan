import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_rks_runtime_operator_pack_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_rks_runtime_operator_pack_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_static_audit(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rows": [
            {
                "scenario": "37",
                "label": "candidate",
                "rks_path": r"C:\RK10\37.rks",
                "rks_exists": True,
                "static_guard_status": "OK_CANDIDATE",
                "existing_status_gate_status": "OK_FOR_SAFE_STOP_TEST",
                "intended_scope": "safe-stop",
                "required_next_gate": "latest clean runtime log",
            },
            {
                "scenario": "38",
                "label": "ng",
                "rks_path": r"C:\RK10\38.rks",
                "rks_exists": True,
                "static_guard_status": "NG",
                "existing_status_gate_status": "NG",
                "intended_scope": "open-build",
                "required_next_gate": "Save As regenerated candidate",
            },
            {
                "scenario": "12/13",
                "label": "no rks",
                "rks_path": "",
                "rks_exists": False,
                "static_guard_status": "N_A_NO_PRIMARY_RKS",
                "existing_status_gate_status": "",
                "intended_scope": "n/a",
                "required_next_gate": "Outlook COM",
            },
            {
                "scenario": "44",
                "label": "prerequisite",
                "rks_path": r"C:\RK10\44.rks",
                "rks_exists": True,
                "static_guard_status": "OK_CANDIDATE",
                "existing_status_gate_status": "",
                "intended_scope": "open-build",
                "required_next_gate": "business OK rows before RKS",
            },
            {
                "scenario": "57",
                "label": "current focus",
                "rks_path": r"C:\RK10\57.rks",
                "rks_exists": True,
                "static_guard_status": "OK_CANDIDATE",
                "existing_status_gate_evidence": r"C:\RK10\reports\57-open-build.tsv",
                "existing_status_gate_exists": True,
                "existing_status_gate_status": "",
                "intended_scope": "open-build",
                "required_next_gate": "no-mail/no-upload/no-write runtime safe-stop and latest clean log",
            },
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_payload_counts_rks_evidence_rows(tmp_path: Path) -> None:
    module = load_module()
    audit_path = tmp_path / "audit.json"
    write_static_audit(audit_path)

    payload = module.build_payload(audit_path, tmp_path / "out", tmp_path / "bundle")

    assert payload["row_count"] == 5
    assert payload["evidence_required_count"] == 2
    assert payload["missing_rks_count"] == 0
    assert payload["no_primary_count"] == 1
    statuses = {row["scenario"]: row["status"] for row in payload["rows"]}
    assert statuses["37"] == "WAITING_OPERATOR_RK10_EVIDENCE"
    assert statuses["38"] == "STATIC_GUARD_NOT_OK"
    assert statuses["12/13"] == "NO_PRIMARY_RKS"
    assert statuses["44"] == "WAITING_PREREQUISITE_BEFORE_RKS_RUNTIME"
    assert statuses["57"] == "WAITING_OPERATOR_RK10_EVIDENCE"
    requires = {row["scenario"]: row["requires_rk10_evidence"] for row in payload["rows"]}
    assert requires["44"] is False
    assert requires["57"] is True


def test_write_outputs_creates_operator_intake_csvs(tmp_path: Path) -> None:
    module = load_module()
    audit_path = tmp_path / "audit.json"
    write_static_audit(audit_path)
    out_dir = tmp_path / "out"
    bundle_dir = tmp_path / "bundle"
    payload = module.build_payload(audit_path, out_dir, bundle_dir)

    module.write_outputs(payload, out_dir, bundle_dir)

    assert (out_dir / "rks_runtime_operator_pack.json").exists()
    assert (out_dir / "rks_runtime_operator_pack.md.numbered").exists()
    assert (out_dir / "rks_runtime_operator_intake.csv").exists()
    assert (bundle_dir / "rks_runtime_operator_intake.csv").exists()
    with (out_dir / "rks_runtime_operator_intake.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["scenario"] == "37"
    assert rows[0]["rk10_editor_open"] == ""
    assert rows[0]["latest_log_path"] == ""


def test_write_outputs_preserves_existing_operator_input(tmp_path: Path) -> None:
    module = load_module()
    audit_path = tmp_path / "audit.json"
    write_static_audit(audit_path)
    out_dir = tmp_path / "out"
    bundle_dir = tmp_path / "bundle"
    out_dir.mkdir()
    bundle_dir.mkdir()
    existing_path = out_dir / "rks_runtime_operator_intake.csv"
    with existing_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "scenario": "37",
                "rks_path": r"C:\RK10\37.rks",
                "operator_decision": "SAFE_STOP_ONLY",
                "rk10_editor_open": "CONFIRMED",
                "rk10_build": "CONFIRMED",
                "runtime_or_safe_stop": "CONFIRMED",
                "latest_log_clean": "YES",
                "latest_log_path": r"C:\logs\37-clean.log",
                "save_as_path": "",
                "operator_name": "operator",
                "checked_at": "2026-06-20T15:10:00",
                "notes": "preserve me",
            }
        )
    payload = module.build_payload(audit_path, out_dir, bundle_dir)

    module.write_outputs(payload, out_dir, bundle_dir)

    with existing_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert payload["preserved_out_intake_row_count"] == 1
    assert rows[0]["operator_decision"] == "SAFE_STOP_ONLY"
    assert rows[0]["rk10_editor_open"] == "CONFIRMED"
    assert rows[0]["latest_log_path"] == r"C:\logs\37-clean.log"
    assert rows[0]["notes"] == "preserve me"


def test_write_outputs_creates_focus_csv_for_unfilled_required_rows(tmp_path: Path) -> None:
    module = load_module()
    audit_path = tmp_path / "audit.json"
    write_static_audit(audit_path)
    out_dir = tmp_path / "out"
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    clean_log_path = tmp_path / "37-clean.log"
    clean_log_path.write_text("RK10 editor open\nRK10 build\nsafe-stop\n", encoding="utf-8")
    existing_path = bundle_dir / "rks_runtime_operator_intake.csv"
    with existing_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "scenario": "37",
                "rks_path": r"C:\RK10\37.rks",
                "operator_decision": "SAFE_STOP_ONLY",
                "rk10_editor_open": "CONFIRMED",
                "rk10_build": "CONFIRMED",
                "runtime_or_safe_stop": "CONFIRMED",
                "latest_log_clean": "YES",
                "latest_log_path": str(clean_log_path),
                "save_as_path": "",
                "operator_name": "operator",
                "checked_at": "2026-06-20T15:10:00",
                "notes": "complete existing row",
            }
        )
    payload = module.build_payload(audit_path, out_dir, bundle_dir)

    module.write_outputs(payload, out_dir, bundle_dir)

    assert payload["current_focus_count"] == 1
    focus_row = payload["current_focus_rows"][0]
    assert focus_row["scenario"] == "57"
    assert "latest_log_path" in focus_row["missing_fields"]
    assert focus_row["known_confirmed_scope"] == "rk10_editor_open, rk10_build_artifact_only"
    assert focus_row["known_evidence_path"] == r"C:\RK10\reports\57-open-build.tsv"
    assert "rk10_editor_open" not in focus_row["remaining_operator_fields"]
    assert "runtime_or_safe_stop" in focus_row["remaining_operator_fields"]
    assert (out_dir / "rks_runtime_operator_focus.csv").exists()
    assert (bundle_dir / "rks_runtime_operator_focus.csv").exists()
    markdown = (out_dir / "rks_runtime_operator_pack.md").read_text(encoding="utf-8")
    assert "Focused Current Runtime Evidence Rows" in markdown
    assert "known_confirmed_scope" in markdown
    assert "rk10_build_artifact_only" in markdown
    assert "validator のみ" in markdown


def test_markdown_separates_static_candidate_from_runtime_ok(tmp_path: Path) -> None:
    module = load_module()
    audit_path = tmp_path / "audit.json"
    write_static_audit(audit_path)
    payload = module.build_payload(audit_path, tmp_path / "out", tmp_path / "bundle")

    markdown = module.build_markdown(payload)

    assert "OK_CANDIDATE" in markdown
    assert "RK10実行OKではない" in markdown
    assert "ButtonRun" in markdown
    assert "latest clean log" in markdown


def test_build_row_defers_existing_ng_status_gate_even_when_static_guard_ok(tmp_path: Path) -> None:
    module = load_module()
    source = {
        "scenario": "38",
        "label": "ng current primary",
        "rks_path": r"C:\RK10\38.rks",
        "rks_exists": True,
        "static_guard_status": "OK_CANDIDATE",
        "existing_status_gate_status": "NG",
        "intended_scope": "open-build",
        "required_next_gate": "RK10 Editor Save As regenerated candidate or Python/BAT entry decision",
    }

    row = module.build_row(source, tmp_path)

    assert row.status == "EXISTING_STATUS_GATE_NG_REGENERATE_OR_ENTRY_DECISION"
    assert row.requires_rk10_evidence is False
