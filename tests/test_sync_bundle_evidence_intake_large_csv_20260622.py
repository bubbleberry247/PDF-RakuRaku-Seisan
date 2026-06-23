import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "sync_bundle_evidence_intake_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "sync_bundle_evidence_intake_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_read_csv_rows_accepts_large_evidence_notes(tmp_path: Path) -> None:
    module = load_module()
    intake_path = tmp_path / "large_intake.csv"
    large_note = "x" * 200_000
    fieldnames = [
        "bundle",
        "scenario",
        "final_evidence_path",
        "operator_result",
        "reviewer",
        "reviewed_at",
        "notes",
    ]
    with intake_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "scenario": "51/52",
                "final_evidence_path": str(tmp_path / "evidence"),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "notes": large_note,
            }
        )

    rows = module.read_csv_rows(intake_path)

    assert rows[0]["scenario"] == "51/52"
    assert rows[0]["notes"] == large_note
