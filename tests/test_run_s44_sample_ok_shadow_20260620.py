import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "run_s44_sample_ok_shadow_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("run_s44_sample_ok_shadow_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_source_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "confirm_ok",
        "reject_reason",
        "vendor_name",
        "amount_estimate",
        "receiving_date",
        "invoice_number",
        "filename",
        "operation_id",
        "pdf_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def source_row(tmp_path: Path, index: int, pdf_exists: bool = True) -> dict[str, str]:
    pdf_path = tmp_path / f"sample-{index}.pdf"
    if pdf_exists:
        pdf_path.write_bytes(b"%PDF-1.4 sample")
    return {
        "confirm_ok": "",
        "reject_reason": "",
        "vendor_name": f"vendor-{index}",
        "amount_estimate": str(100 + index),
        "receiving_date": "20260131",
        "invoice_number": f"T{index:013d}",
        "filename": pdf_path.name,
        "operation_id": f"operation-{index}",
        "pdf_path": str(pdf_path),
    }


def test_build_sample_csv_marks_limited_rows_ok(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "source.csv"
    write_source_csv(
        source_csv,
        [source_row(tmp_path, 1), source_row(tmp_path, 2), source_row(tmp_path, 3)],
    )

    result = module.build_sample_csv(source_csv, tmp_path / "out", ok_limit=2)

    assert result.status == "READY_FOR_SHADOW_HANDOFF"
    assert result.sample_ok_count == 2
    assert result.sample_ng_count == 1
    with Path(result.sample_csv).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["confirm_ok"] for row in rows] == ["OK", "OK", "NG"]
    assert rows[0]["reject_reason"] == "sample shadow handoff only; not business approval"


def test_build_sample_csv_skips_missing_pdf(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "source.csv"
    write_source_csv(
        source_csv,
        [source_row(tmp_path, 1, pdf_exists=False), source_row(tmp_path, 2)],
    )

    result = module.build_sample_csv(source_csv, tmp_path / "out", ok_limit=1)

    assert result.status == "READY_FOR_SHADOW_HANDOFF"
    assert result.sample_ok_count == 1
    assert result.sample_ng_count == 1
    assert result.skipped_missing_pdf_count == 1


def test_build_markdown_states_sample_is_not_approval(tmp_path: Path) -> None:
    module = load_module()
    result = module.SampleBuildResult(
        generated_at="2026-06-20T00:00:00",
        source_csv=str(tmp_path / "source.csv"),
        sample_csv=str(tmp_path / "sample.csv"),
        source_exists=True,
        source_row_count=1,
        requested_ok_limit=1,
        sample_ok_count=1,
        sample_ng_count=0,
        skipped_missing_pdf_count=0,
        status="READY_FOR_SHADOW_HANDOFF",
        next_action="run",
    )

    markdown = module.build_markdown(result, {"shadow_handoff": {"generated": False}})

    assert "OK marks in the sample CSV are test input only" in markdown
    assert "Live review.db" in markdown
