import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_external_approval_runbook_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_external_approval_runbook_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_packet_payload() -> dict:
    return {
        "approval_bundle_count": 2,
        "packets": [
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "owner": "PC/Outlook管理者",
                "scenarios": "12/13",
                "allowed_operations": "--check-outlook-com then dry-run",
                "hard_stops": "mail/print",
                "csv_path": r"C:\bundle\outlook.csv",
            },
            {
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "owner": "RK10操作担当者",
                "scenarios": "37, 38",
                "allowed_operations": "open/build only",
                "hard_stops": "ButtonRun",
                "csv_path": r"C:\bundle\rk10.csv",
            },
        ],
    }


def test_build_payload_marks_outlook_as_next_single_approval(tmp_path: Path) -> None:
    module = load_module()

    payload = module.build_payload(sample_packet_payload(), tmp_path)

    assert payload["next_single_approval"] == "OUTLOOK_COM_BUNDLE"
    assert payload["external_approval_step_count"] == 2
    commands = [step["command"] for step in payload["steps"]]
    assert any("--check-outlook-com" in command for command in commands)
    assert any("--scan-only" in command for command in commands)
    assert all("--execute" not in command for command in commands)
    assert all("--print" not in command for command in commands)


def test_build_payload_marks_business_review_next_when_outlook_dryrun_ok(tmp_path: Path) -> None:
    module = load_module()
    log_dir = tmp_path / "outlook_com_bundle_logs"
    log_dir.mkdir()
    (log_dir / "summary.txt").write_text(
        "check_outlook_com_exit=0\nscan_only_dryrun_exit=0\n",
        encoding="utf-8",
    )

    payload = module.build_payload(sample_packet_payload(), tmp_path)
    markdown = module.build_markdown(payload)

    assert payload["next_single_approval"] == "BUSINESS_REVIEW_BUNDLE"
    assert payload["external_approval_step_count"] == 0
    assert payload["last_outlook_result"]["status"] == "OUTLOOK_SCAN_ONLY_DRYRUN_OK"
    assert "OUTLOOK_COM_BUNDLEはCOM check/scan-only dry-runが成功済み" in markdown
    assert "operator_result" in markdown


def test_build_outlook_script_has_no_irreversible_flags(tmp_path: Path) -> None:
    module = load_module()

    script = module.build_outlook_script(tmp_path)
    command_lines = [
        line for line in script.splitlines()
        if line.strip().startswith("& $Python")
    ]

    assert "--check-outlook-com" in script
    assert "--scan-only" in script
    assert "--dry-run-mail" in script
    assert all("--execute" not in line for line in command_lines)
    assert all("--print" not in line for line in command_lines)


def test_write_outputs_creates_runbook_files(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(sample_packet_payload(), tmp_path)

    module.write_outputs(payload, tmp_path)

    assert (tmp_path / "external_approval_runbook.json").exists()
    assert (tmp_path / "external_approval_runbook.md").exists()
    assert (tmp_path / "external_approval_runbook.md.numbered").exists()
    assert (tmp_path / "outlook_com_recovery_checklist.md").exists()
    assert (tmp_path / "outlook_com_recovery_checklist.md.numbered").exists()
    assert (tmp_path / "rk10_editor_recovery_checklist.md").exists()
    assert (tmp_path / "rk10_editor_recovery_checklist.md.numbered").exists()
    assert (tmp_path / "outlook_com_bundle_dryrun.ps1").exists()
    csv_path = tmp_path / "external_approval_steps.csv"
    assert csv_path.exists()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[1]["bundle"] == "OUTLOOK_COM_BUNDLE"
    assert rows[1]["requires_external_approval"] == "True"
    raw_script = (tmp_path / "outlook_com_bundle_dryrun.ps1").read_bytes()
    assert raw_script.startswith(b"\xef\xbb\xbf")


def test_build_outlook_recovery_checklist_keeps_hard_stops(tmp_path: Path) -> None:
    module = load_module()
    log_dir = tmp_path / "outlook_com_bundle_logs"
    log_dir.mkdir()
    (log_dir / "summary.txt").write_text(
        "check_outlook_com_exit=2\nscan_only_dryrun_exit=SKIPPED\n",
        encoding="utf-8",
    )
    payload = module.build_payload(sample_packet_payload(), tmp_path)

    checklist = module.build_outlook_recovery_checklist(payload)

    assert "manual recovery guide only" in checklist
    assert "強制終了しない" in checklist
    assert "--execute" in checklist
    assert "--print" in checklist
    assert "scan_only_dryrun_exit=0" in checklist


def test_build_rk10_recovery_checklist_keeps_hard_stops(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(sample_packet_payload(), tmp_path)

    checklist = module.build_rk10_recovery_checklist(payload)

    assert "manual recovery guide only" in checklist
    assert "RK10ライセンス有効期限警告" in checklist
    assert "ButtonRun" in checklist
    assert "RunScenario" in checklist
    assert "63対照" in checklist
    assert "58" in checklist


def test_build_last_outlook_result_classifies_com_failure(tmp_path: Path) -> None:
    module = load_module()
    log_dir = tmp_path / "outlook_com_bundle_logs"
    log_dir.mkdir()
    (log_dir / "summary.txt").write_text(
        "check_outlook_com_exit=2\nscan_only_dryrun_exit=SKIPPED\n",
        encoding="utf-8",
    )
    (log_dir / "01_check_outlook_com.log").write_text(
        "com_error(-2147221021, 'x', None, None)\n"
        "com_error(-2146959355, 'y', None, None)\n",
        encoding="utf-8",
    )

    result = module.build_last_outlook_result(tmp_path)

    assert result["status"] == "OUTLOOK_COM_NOT_ATTACHABLE_OR_STARTABLE"
    assert result["check_outlook_com_exit"] == "2"
    assert result["scan_only_dryrun_exit"] == "SKIPPED"


def test_build_last_outlook_result_reads_utf16_powershell_logs(tmp_path: Path) -> None:
    module = load_module()
    log_dir = tmp_path / "outlook_com_bundle_logs"
    log_dir.mkdir()
    (log_dir / "summary.txt").write_text(
        "check_outlook_com_exit=2\nscan_only_dryrun_exit=SKIPPED\n",
        encoding="utf-8",
    )
    (log_dir / "01_check_outlook_com.log").write_text(
        "com_error(-2146959355, 'server failed', None, None)\n",
        encoding="utf-16",
    )

    result = module.build_last_outlook_result(tmp_path)

    assert result["status"] == "OUTLOOK_COM_CHECK_FAILED"
    assert result["hresult_codes"] == ["-2146959355"]
