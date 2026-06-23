import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "run_s44_quick_bucket_ok_simulation_20260621.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("run_s44_quick_bucket_ok_simulation_20260621", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sample_row(
    tmp_path: Path,
    operation_id: str,
    amount: str,
    filename_amount: str,
) -> dict[str, str]:
    pdf_path = tmp_path / f"{operation_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 sample")
    return {
        "confirm_ok": "",
        "reject_reason": "",
        "vendor_name": "テスト商事",
        "amount_estimate": amount,
        "receiving_date": "20260131",
        "invoice_number": "T1234567890123",
        "filename": f"{operation_id}_テスト商事_202601_{filename_amount}.pdf",
        "operation_id": operation_id,
        "pdf_path": str(pdf_path),
    }


def test_build_result_runs_quick_bucket_simulation_without_source_write(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    out_dir = tmp_path / "out"
    write_csv(
        source_csv,
        [
            sample_row(tmp_path, "quick-1", "100", "100"),
            sample_row(tmp_path, "zero-1", "0", "500"),
            sample_row(tmp_path, "mismatch-1", "100", "500"),
        ],
    )
    source_before = source_csv.read_text(encoding="utf-8-sig")

    result = module.build_result(source_csv, out_dir)
    module.write_outputs(result, out_dir)

    assert result.status == "READY_FOR_SHADOW_HANDOFF"
    assert result.source_unchanged is True
    assert source_csv.read_text(encoding="utf-8-sig") == source_before
    assert result.ok_count == 1
    assert result.blank_count == 2
    assert result.bucket_decision_overlay_applied_count == 1
    assert result.shadow_handoff_generated is True
    assert result.shadow_handoff_verified is True
    assert result.shadow_handoff_item_count == 1
    assert module.SIMULATION_REVIEWER in Path(result.simulation_seed_csv).read_text(
        encoding="utf-8-sig"
    )
    assert (out_dir / "s44_quick_bucket_ok_simulation.md.numbered").exists()
