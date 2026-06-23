import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "run_s70_sample_confirm_preview_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("run_s70_sample_confirm_preview_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_sample_inventory_selects_two_bulk_transfer_records() -> None:
    module = load_module()

    inventory = module.build_sample_inventory(module.DEFAULT_PAYMENT_DATE)
    selected, anomalies, manual_excluded = module.classify_records(inventory, module.DEFAULT_PAYMENT_DATE)

    assert len(inventory) == 3
    assert len(selected) == 2
    assert len(anomalies) == 0
    assert len(manual_excluded) == 1
    assert sum(record.amount_yen or 0 for record in selected) == module.EXPECTED_TOTAL_AMOUNT_YEN


def test_run_sample_confirm_preview_writes_safe_report(tmp_path: Path) -> None:
    module = load_module()

    payload = module.run_sample_confirm_preview(tmp_path)

    assert payload["status"] == "CONFIRM_PREVIEW_SAMPLE_OK"
    assert payload["selected_records"] == 2
    assert payload["selected_total_amount_yen"] == module.EXPECTED_TOTAL_AMOUNT_YEN
    assert payload["confirmation_ok_pressed"] is False
    assert payload["payment_execute_performed"] is False
    assert Path(payload["selected_csv"]).exists()
    assert (tmp_path / "s70_sample_confirm_preview.md.numbered").exists()


def test_build_markdown_states_payment_is_not_executed(tmp_path: Path) -> None:
    module = load_module()
    payload = module.run_sample_confirm_preview(tmp_path)
    result = module.SampleConfirmPreviewResult(**payload)

    markdown = module.build_markdown(result)

    assert "Confirmation dialog OK is not pressed" in markdown
    assert "Payment execution" in markdown
