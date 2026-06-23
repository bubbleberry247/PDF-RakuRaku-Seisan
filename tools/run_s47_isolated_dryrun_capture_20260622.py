from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import shutil
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook


SCENARIO_ROOT = Path(r"C:\ProgramData\RK10\Robots\47出退勤確認")
SOURCE_CONFIG_DIR = SCENARIO_ROOT / "config"
SOURCE_WORK_DIR = SCENARIO_ROOT / "work"
SOURCE_SCRIPT_DIR = SCENARIO_ROOT / "script"
DEFAULT_REPORT_ROOT = Path(
    r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports"
    r"\s47_current_isolated_dryrun_recheck_20260622"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as binary_handle:
        for chunk in iter(lambda: binary_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_csv_rows(path: Path, *, has_header: bool) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as csv_handle:
        if has_header:
            reader = csv.DictReader(csv_handle)
            return sum(1 for _row in reader)
        reader = csv.reader(csv_handle)
        return sum(1 for _row in reader)


def number_file(path: Path) -> None:
    if not path.exists() or path.is_dir():
        return
    numbered = path.with_name(path.name + ".numbered")
    line_number = 0
    with path.open("r", encoding="utf-8", errors="replace") as source_handle:
        with numbered.open("w", encoding="utf-8", newline="\n") as numbered_handle:
            for line in source_handle:
                line_number += 1
                numbered_handle.write(f"{line_number}: {line.rstrip()}\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def create_sample_config(sample_root: Path) -> tuple[Path, Path, Path, Path]:
    config_dir = sample_root / "config"
    work_dir = sample_root / "work"
    input_dir = sample_root / "input"
    config_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)

    for file_name in ("employee_master.csv", "kbn_master.csv", "mail_template_master.csv"):
        shutil.copy2(SOURCE_CONFIG_DIR / file_name, config_dir / file_name)

    (config_dir / "env.txt").write_text("LOCAL\n", encoding="utf-8")

    flag_list_path = work_dir / "flag_list.csv"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["key", "value"])
    rows = [
        ("従業員マスタCSV_パス", "employee_master.csv"),
        ("勤務区分マスタCSV_パス", "kbn_master.csv"),
        ("メールテンプレCSV_パス", "mail_template_master.csv"),
        ("フラグ一覧CSV_パス", str(flag_list_path)),
        ("AUTO_UPLOAD", "0"),
        ("RECORU_TOKEN_CREDENTIAL_TARGET", "RK10_SAMPLE_NO_TOKEN"),
    ]
    for key, value in rows:
        worksheet.append([key, value])
    workbook.save(config_dir / "RK10_config_LOCAL.xlsx")

    return config_dir, work_dir, input_dir, flag_list_path


def run_recoru_batch(config_dir: Path, work_dir: Path, target_date: str, input_json: Path) -> dict:
    recoru_batch = load_module("s47_recoru_batch_20260622", SOURCE_SCRIPT_DIR / "recoru_batch.py")
    recoru_batch.LOG_PATH = work_dir / "recoru_batch.log"

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    previous_argv = sys.argv[:]
    sys.argv = [
        str(SOURCE_SCRIPT_DIR / "recoru_batch.py"),
        str(config_dir),
        target_date,
        str(input_json),
        "--dry-run",
        "--no-upload",
        "--no-ensure-outlook",
    ]
    exit_code = 0
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        try:
            recoru_batch.main()
        except SystemExit as system_exit:
            exit_code = int(system_exit.code or 0)
        finally:
            sys.argv = previous_argv

    stdout_path = work_dir / "recoru_batch.stdout.txt"
    stderr_path = work_dir / "recoru_batch.stderr.txt"
    stdout_path.write_text(stdout_buffer.getvalue(), encoding="utf-8")
    stderr_path.write_text(stderr_buffer.getvalue(), encoding="utf-8")
    return {"exit_code": exit_code, "stdout": str(stdout_path), "stderr": str(stderr_path)}


def run_mail_dryrun(config_dir: Path, work_dir: Path, target_date: str, flag_list_path: Path, manifest_path: Path, max_send: int) -> dict:
    if str(SOURCE_SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SOURCE_SCRIPT_DIR))
    send_error_mail = load_module("s47_send_error_mail_20260622", SOURCE_SCRIPT_DIR / "send_error_mail.py")

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    send_log_path = work_dir / "send_log.csv"
    arguments = [
        "--config-dir",
        str(config_dir),
        "--flag-list",
        str(flag_list_path),
        "--send-log",
        str(send_log_path),
        "--target-date",
        target_date,
        "--max-send",
        str(max_send),
        "--manifest",
        str(manifest_path),
    ]
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        exit_code = send_error_mail.main(arguments)

    stdout_path = work_dir / "send_error_mail.stdout.txt"
    stderr_path = work_dir / "send_error_mail.stderr.txt"
    stdout_path.write_text(stdout_buffer.getvalue(), encoding="utf-8")
    stderr_path.write_text(stderr_buffer.getvalue(), encoding="utf-8")
    return {"exit_code": exit_code, "stdout": str(stdout_path), "stderr": str(stderr_path)}


def write_manifest(work_dir: Path, flag_list_path: Path, target_date: str, batch_exit_code: int) -> Path:
    if str(SOURCE_SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SOURCE_SCRIPT_DIR))
    flag_manifest = load_module("s47_flag_manifest_20260622", SOURCE_SCRIPT_DIR / "flag_manifest.py")
    manifest_path = work_dir / "flag_list.manifest.json"
    flag_manifest.write_manifest(flag_list_path, manifest_path, target_date, batch_exit_code)
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scenario 47 isolated safe dry-run capture")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--target-date", default="20260616")
    parser.add_argument("--json-source", type=Path)
    parser.add_argument("--max-send", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_root = args.report_root
    sample_root = report_root / "sample_run"
    if sample_root.exists():
        shutil.rmtree(sample_root)
    sample_root.mkdir(parents=True, exist_ok=True)

    config_dir, work_dir, input_dir, flag_list_path = create_sample_config(sample_root)
    json_source = args.json_source or SOURCE_WORK_DIR / f"recoru_workdays_{args.target_date}.json"
    if not json_source.exists():
        raise FileNotFoundError(json_source)
    input_json = input_dir / json_source.name
    shutil.copy2(json_source, input_json)

    batch_result = run_recoru_batch(config_dir, work_dir, args.target_date, input_json)
    flag_hash_after_batch = sha256_file(flag_list_path) if flag_list_path.exists() else ""
    manifest_path = write_manifest(work_dir, flag_list_path, args.target_date, batch_result["exit_code"])
    mail_result = run_mail_dryrun(
        config_dir=config_dir,
        work_dir=work_dir,
        target_date=args.target_date,
        flag_list_path=flag_list_path,
        manifest_path=manifest_path,
        max_send=args.max_send,
    )
    flag_hash_after_mail = sha256_file(flag_list_path) if flag_list_path.exists() else ""

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scope": "isolated LOCAL sample; dry-run/no-upload/no-send/no-outlook-prewarm",
        "scenario_root": str(SCENARIO_ROOT),
        "sample_root": str(sample_root),
        "target_date": args.target_date,
        "json_source": str(json_source),
        "input_json": str(input_json),
        "config_dir": str(config_dir),
        "work_dir": str(work_dir),
        "flag_list": str(flag_list_path),
        "manifest": str(manifest_path),
        "send_log": str(work_dir / "send_log.csv"),
        "batch": batch_result,
        "mail": mail_result,
        "flag_rows": count_csv_rows(flag_list_path, has_header=True),
        "send_log_rows": count_csv_rows(work_dir / "send_log.csv", has_header=False),
        "flag_sha256_after_batch": flag_hash_after_batch,
        "flag_sha256_after_mail": flag_hash_after_mail,
        "flag_unchanged_by_mail_dryrun": flag_hash_after_batch == flag_hash_after_mail,
    }
    summary_path = report_root / "s47_isolated_dryrun_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for output_path in [
        summary_path,
        work_dir / "recoru_batch.stdout.txt",
        work_dir / "recoru_batch.stderr.txt",
        work_dir / "recoru_batch.log",
        work_dir / "send_error_mail.stdout.txt",
        work_dir / "send_error_mail.stderr.txt",
        flag_list_path,
        manifest_path,
        work_dir / "send_log.csv",
    ]:
        number_file(output_path)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if batch_result["exit_code"] == 0 and mail_result["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
