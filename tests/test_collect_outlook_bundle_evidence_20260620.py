import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "collect_outlook_bundle_evidence_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("collect_outlook_bundle_evidence_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_intake(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "bundle",
                "scenario",
                "required_final_evidence",
                "current_reference_evidence",
                "final_evidence_path",
                "operator_result",
                "reviewer",
                "reviewed_at",
                "rakuraku_customer_login_used",
                "temporary_save_created",
                "created_data_cleanup_status",
                "created_data_cleanup_evidence_path",
                "cleanup_reviewer",
                "cleanup_reviewed_at",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "scenario": "12/13",
                "required_final_evidence": "COM check exit 0、dry-runログ",
                "current_reference_evidence": r"C:\tool.py",
            }
        )


def test_build_payload_does_not_update_when_scan_skipped(tmp_path: Path) -> None:
    module = load_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "summary.txt").write_text(
        "check_outlook_com_exit=2\nscan_only_dryrun_exit=SKIPPED\n",
        encoding="utf-8",
    )
    intake_path = tmp_path / "pack" / "final_evidence_intake.csv"
    write_intake(intake_path)

    payload = module.build_payload(log_dir, intake_path, tmp_path / "pack" / "final_evidence", apply_updates=True)

    assert payload["ready_for_intake"] is False
    assert payload["updated_intake"] is False
    assert "CHECK_EXIT_2" in payload["status"]
    assert "SCAN_EXIT_SKIPPED" in payload["status"]


def test_build_payload_updates_intake_when_both_steps_exit_zero(tmp_path: Path) -> None:
    module = load_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "summary.txt").write_text(
        "\ufeffOUTLOOK_COM_BUNDLE safety: no --execute, no --print, no mail send, no state change\n"
        "check_outlook_com_exit=0\n"
        "scan_only_dryrun_exit=0\n",
        encoding="utf-8",
    )
    (log_dir / "01_check_outlook_com.log").write_text("COM OK\n", encoding="utf-8")
    (log_dir / "02_scan_only_dryrun.log").write_text(
        "scan-only dry-run complete\nsaved=0\nprinted=0\nmail_sent=0\n",
        encoding="utf-8",
    )
    pack_dir = tmp_path / "pack"
    intake_path = pack_dir / "final_evidence_intake.csv"
    final_dir = pack_dir / "final_evidence"
    write_intake(intake_path)

    payload = module.build_payload(log_dir, intake_path, final_dir, apply_updates=True)

    assert payload["ready_for_intake"] is True
    assert payload["updated_intake"] is True
    evidence_path = Path(payload["evidence_file"])
    assert evidence_path.exists()
    assert evidence_path.is_dir()
    evidence_names = sorted(path.name for path in evidence_path.iterdir())
    assert any(name.startswith("scenario_12_13_outlook_com_preflight_exit0_") for name in evidence_names)
    assert any(name.startswith("scenario_12_13_dryrun_no_print_no_mail_") for name in evidence_names)
    assert any(name.startswith("scenario_12_13_saved_pdf_count_summary_") for name in evidence_names)
    with intake_path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["final_evidence_path"] == str(evidence_path)
    assert row["operator_result"] == ""
    assert row["reviewer"] == ""
    assert row["reviewed_at"] == ""
    assert row["temporary_save_created"] == "NO"


def test_build_payload_clears_legacy_auto_approval_fields(tmp_path: Path) -> None:
    module = load_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "summary.txt").write_text(
        "\ufeffOUTLOOK_COM_BUNDLE safety: no --execute, no --print, no mail send, no state change\n"
        "check_outlook_com_exit=0\n"
        "scan_only_dryrun_exit=0\n",
        encoding="utf-8",
    )
    (log_dir / "01_check_outlook_com.log").write_text("COM OK\n", encoding="utf-8")
    (log_dir / "02_scan_only_dryrun.log").write_text(
        "scan-only dry-run complete\nsaved=0\nprinted=0\nmail_sent=0\n",
        encoding="utf-8",
    )
    intake_path = tmp_path / "pack" / "final_evidence_intake.csv"
    write_intake(intake_path)
    with intake_path.open("r", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(csv.DictReader(handle).fieldnames or [])
    with intake_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["operator_result"] = "OK"
    rows[0]["reviewer"] = "OUTLOOK_COM_BUNDLE_AUTO_COLLECTOR"
    rows[0]["reviewed_at"] = "2026-06-22T00:13:12"
    rows[0]["notes"] = module.SYNC_NOTE
    with intake_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    payload = module.build_payload(
        log_dir,
        intake_path,
        tmp_path / "pack" / "final_evidence",
        apply_updates=True,
    )

    with intake_path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert payload["updated_intake"] is True
    assert row["operator_result"] == ""
    assert row["reviewer"] == ""
    assert row["reviewed_at"] == ""
    assert module.LEGACY_CLEAR_NOTE in row["notes"]


def test_build_payload_blocks_forbidden_keywords_in_success_log(tmp_path: Path) -> None:
    module = load_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "summary.txt").write_text(
        "check_outlook_com_exit=0\nscan_only_dryrun_exit=0\n",
        encoding="utf-8",
    )
    (log_dir / "01_check_outlook_com.log").write_text("COM OK\n", encoding="utf-8")
    (log_dir / "02_scan_only_dryrun.log").write_text("--print executed\n", encoding="utf-8")
    intake_path = tmp_path / "pack" / "final_evidence_intake.csv"
    write_intake(intake_path)

    payload = module.build_payload(log_dir, intake_path, tmp_path / "pack" / "final_evidence", apply_updates=True)

    assert payload["ready_for_intake"] is False
    assert payload["updated_intake"] is False
    assert "FORBIDDEN_KEYWORDS_FOUND" in payload["status"]
