import importlib.util
import csv
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_bundle_evidence_packs_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_bundle_evidence_packs_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_packet(path: Path, evidence_file: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "packets": [
                    {
                        "bundle": "BUSINESS_REVIEW_BUNDLE",
                        "owner": "業務担当者",
                        "scenarios": "44",
                        "evidence_to_capture": "OK/NG CSV and handoff log",
                        "hard_stops": "Rakuraku",
                    },
                    {
                        "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                        "owner": "RK10操作担当者",
                        "scenarios": "37, 38",
                        "evidence_to_capture": "open/build logs",
                        "hard_stops": "ButtonRun",
                    },
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "owner": "PC/Outlook管理者",
                        "scenarios": "12/13",
                        "evidence_to_capture": "COM check and dry-run log",
                        "hard_stops": "no mail/no print",
                    },
                ],
                "source_map": {
                    "44": str(evidence_file),
                    "37": str(evidence_file),
                    "12/13": str(evidence_file),
                },
                "current_evidence_map": {
                    "44": str(evidence_file),
                    "38": str(path.parent / "missing.md"),
                    "12/13": str(evidence_file),
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_build_payload_creates_bundle_pack_metadata(tmp_path: Path) -> None:
    module = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok", encoding="utf-8")
    packet_path = tmp_path / "packet.json"
    write_packet(packet_path, evidence_file)

    payload = module.build_payload(packet_path, tmp_path / "packs")

    assert payload["bundle_count"] == 3
    assert payload["scenario_count"] == 4
    assert payload["packs"][0]["bundle"] == "BUSINESS_REVIEW_BUNDLE"
    scenario_row = payload["packs"][0]["scenario_evidence"][0]
    assert scenario_row["source_exists"] is True
    assert scenario_row["current_reference_exists"] is True


def test_write_outputs_creates_manifest_and_checklist(tmp_path: Path) -> None:
    module = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok", encoding="utf-8")
    packet_path = tmp_path / "packet.json"
    out_dir = tmp_path / "packs"
    write_packet(packet_path, evidence_file)
    payload = module.build_payload(packet_path, out_dir)

    module.write_outputs(payload, out_dir)

    pack_dir = out_dir / "business_review_bundle"
    assert (pack_dir / "evidence_manifest.json").exists()
    assert (pack_dir / "final_evidence").exists()
    assert (pack_dir / "final_evidence" / "scenario_44").exists()
    assert (pack_dir / "final_evidence_intake.csv").exists()
    assert (pack_dir / "reference_evidence_snapshot.csv").exists()
    assert (pack_dir / "operator_evidence_filename_template.csv").exists()
    assert (pack_dir / "operator_evidence_filename_template.md").exists()
    assert not (pack_dir / "final_evidence" / "operator_evidence_filename_template.csv").exists()
    intake_text = (pack_dir / "final_evidence_intake.csv").read_text(
        encoding="utf-8-sig"
    )
    assert "suggested_final_evidence_folder" in intake_text
    assert "required_update_fields" in intake_text
    assert "hard_stops" in intake_text
    assert "final_evidence\\scenario_44" in intake_text
    assert "created_data_cleanup_evidence_path" in intake_text
    with (pack_dir / "final_evidence_intake.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        intake_rows = list(csv.DictReader(handle))
    assert intake_rows[0]["hard_stops"] == "Rakuraku"
    assert intake_rows[0]["required_update_fields"] == (
        "final_evidence_path, operator_result, reviewer, reviewed_at"
    )
    assert intake_rows[0]["final_evidence_path"] == ""
    snapshot = (pack_dir / "reference_evidence_snapshot.csv").read_text(encoding="utf-8-sig")
    assert "REFERENCE_ONLY_NOT_FINAL" in snapshot
    assert "final_evidence_allowed" in snapshot
    checklist = pack_dir / "operator_evidence_checklist.md"
    assert checklist.exists()
    assert "not approvals by themselves" not in checklist.read_text(encoding="utf-8")
    assert "prepared evidence container" in checklist.read_text(encoding="utf-8")
    assert "suggested_final_evidence_folder" in checklist.read_text(encoding="utf-8")
    assert "final_evidence_intake.csv" in checklist.read_text(encoding="utf-8")
    assert "reference_evidence_snapshot.csv" in checklist.read_text(encoding="utf-8")
    assert "operator_evidence_filename_template.csv" in checklist.read_text(encoding="utf-8")
    assert "must not be used as final approval evidence" in checklist.read_text(encoding="utf-8")
    assert "do not use the prepared pack root as final evidence" in checklist.read_text(encoding="utf-8")
    template_text = (pack_dir / "operator_evidence_filename_template.csv").read_text(encoding="utf-8-sig")
    assert "template_only_not_final_evidence" in template_text
    assert "scenario_44_safe_run_log_YYYYMMDD_HHMMSS.txt" in template_text


def test_rk10_bundle_checklist_includes_focused_runtime_csv(tmp_path: Path) -> None:
    module = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok", encoding="utf-8")
    packet_path = tmp_path / "packet.json"
    out_dir = tmp_path / "packs"
    write_packet(packet_path, evidence_file)
    payload = module.build_payload(packet_path, out_dir)

    module.write_outputs(payload, out_dir)

    rk10_checklist = out_dir / "rk10_editor_runtime_bundle" / "operator_evidence_checklist.md"
    business_checklist = out_dir / "business_review_bundle" / "operator_evidence_checklist.md"
    rk10_text = rk10_checklist.read_text(encoding="utf-8")
    business_text = business_checklist.read_text(encoding="utf-8")
    assert "Focused RKS Runtime Evidence" in rk10_text
    assert "rks_runtime_operator_focus.csv" in rk10_text
    assert "最終OK判定" in rk10_text
    assert "Focused RKS Runtime Evidence" not in business_text


def test_filename_template_includes_outlook_and_rk10_names(tmp_path: Path) -> None:
    module = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok", encoding="utf-8")
    packet_path = tmp_path / "packet.json"
    out_dir = tmp_path / "packs"
    write_packet(packet_path, evidence_file)
    payload = module.build_payload(packet_path, out_dir)

    module.write_outputs(payload, out_dir)

    outlook_text = (
        out_dir / "outlook_com_bundle" / "operator_evidence_filename_template.csv"
    ).read_text(encoding="utf-8-sig")
    rk10_text = (
        out_dir / "rk10_editor_runtime_bundle" / "operator_evidence_filename_template.csv"
    ).read_text(encoding="utf-8-sig")
    assert "scenario_12_13_outlook_com_preflight_exit0_YYYYMMDD_HHMMSS.txt" in outlook_text
    assert "scenario_12_13_dryrun_no_print_no_mail_YYYYMMDD_HHMMSS.log" in outlook_text
    assert "template_only_not_final_evidence" in outlook_text
    assert "scenario_37_rk10_metadata_guard_YYYYMMDD_HHMMSS.txt" in rk10_text
    assert "scenario_38_safe_stop_latest_clean_log_YYYYMMDD_HHMMSS.txt" in rk10_text
    assert "template_only_not_final_evidence" in rk10_text



def test_write_outputs_preserves_existing_final_evidence_intake_fields(tmp_path: Path) -> None:
    module = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok", encoding="utf-8")
    packet_path = tmp_path / "packet.json"
    out_dir = tmp_path / "packs"
    write_packet(packet_path, evidence_file)
    payload = module.build_payload(packet_path, out_dir)
    pack_dir = out_dir / "outlook_com_bundle"
    pack_dir.mkdir(parents=True)
    intake_path = pack_dir / "final_evidence_intake.csv"
    with intake_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.INTAKE_FIELDNAMES)
        writer.writeheader()
        writer.writerow(
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "scenario": "12/13",
                "required_final_evidence": "old",
                "hard_stops": "old",
                "current_reference_evidence": "old",
                "suggested_final_evidence_folder": "old",
                "final_evidence_path": str(tmp_path / "final"),
                "required_update_fields": "old",
                "operator_result": "OK",
                "reviewer": "operator",
                "reviewed_at": "2026-06-22T20:00:00",
                "rakuraku_customer_login_used": "NO",
                "temporary_save_created": "NO",
                "created_data_cleanup_status": "",
                "created_data_cleanup_evidence_path": "",
                "cleanup_reviewer": "",
                "cleanup_reviewed_at": "",
                "notes": "keep me",
            }
        )

    module.write_outputs(payload, out_dir)

    with intake_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["operator_result"] == "OK"
    assert rows[0]["reviewer"] == "operator"
    assert rows[0]["reviewed_at"] == "2026-06-22T20:00:00"
    assert rows[0]["final_evidence_path"] == str(tmp_path / "final")
    assert rows[0]["notes"] == "keep me"
    assert rows[0]["required_final_evidence"] == "COM check and dry-run log"

def test_summary_markdown_states_boundary(tmp_path: Path) -> None:
    module = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok", encoding="utf-8")
    packet_path = tmp_path / "packet.json"
    write_packet(packet_path, evidence_file)
    payload = module.build_payload(packet_path, tmp_path / "packs")

    markdown = module.build_summary_markdown(payload)

    assert "# 6束証跡パック 2026-06-20" in markdown
    assert "They do not prove production completion" in markdown
