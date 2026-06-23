import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "sync_execution_packet_candidate_evidence_paths_20260621.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "sync_execution_packet_candidate_evidence_paths_20260621_operator_fields",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def unified_fieldnames() -> list[str]:
    return [
        "entry_key",
        "bundle",
        "scenario",
        "final_evidence_path",
        "operator_result",
        "reviewer",
        "reviewed_at",
    ]


def packet_fieldnames() -> list[str]:
    return [
        "scenario",
        "bundle",
        "operator_result",
        "evidence_path",
        "reviewer",
        "reviewed_at",
    ]


def test_sync_copies_complete_operator_stamp_into_blank_packet_fields(
    tmp_path: Path,
) -> None:
    module = load_module()
    candidate_dir = tmp_path / "final_evidence" / "scenario_37"
    candidate_dir.mkdir(parents=True)
    unified_csv = tmp_path / "unified.csv"
    packet_dir = tmp_path / "packets"
    packet_csv = packet_dir / "rk10_editor_runtime_bundle.csv"
    write_csv(
        unified_csv,
        unified_fieldnames(),
        [
            {
                "entry_key": "RK10_EDITOR_RUNTIME_BUNDLE::37",
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "scenario": "37",
                "final_evidence_path": str(candidate_dir),
                "operator_result": "OK",
                "reviewer": "status_gate_import_20260618",
                "reviewed_at": "2026-06-18T10:18:53",
            }
        ],
    )
    write_csv(
        packet_csv,
        packet_fieldnames(),
        [
            {
                "scenario": "37",
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "operator_result": "",
                "evidence_path": str(candidate_dir),
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )

    payload = module.build_payload(unified_csv, packet_dir, apply_updates=True)

    rows = read_csv(packet_csv)
    assert payload["updated_row_count"] == 1
    assert payload["operator_field_sync_row_count"] == 1
    assert rows[0]["evidence_path"] == str(candidate_dir)
    assert rows[0]["operator_result"] == "OK"
    assert rows[0]["reviewer"] == "status_gate_import_20260618"
    assert rows[0]["reviewed_at"] == "2026-06-18T10:18:53"


def test_sync_does_not_copy_partial_operator_stamp(tmp_path: Path) -> None:
    module = load_module()
    candidate_dir = tmp_path / "final_evidence" / "scenario_57"
    candidate_dir.mkdir(parents=True)
    unified_csv = tmp_path / "unified.csv"
    packet_dir = tmp_path / "packets"
    packet_csv = packet_dir / "rk10_editor_runtime_bundle.csv"
    write_csv(
        unified_csv,
        unified_fieldnames(),
        [
            {
                "entry_key": "RK10_EDITOR_RUNTIME_BUNDLE::57",
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "scenario": "57",
                "final_evidence_path": str(candidate_dir),
                "operator_result": "OK",
                "reviewer": "",
                "reviewed_at": "2026-06-22T20:03:06",
            }
        ],
    )
    write_csv(
        packet_csv,
        packet_fieldnames(),
        [
            {
                "scenario": "57",
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )

    payload = module.build_payload(unified_csv, packet_dir, apply_updates=True)

    rows = read_csv(packet_csv)
    assert payload["updated_row_count"] == 1
    assert payload["operator_field_sync_row_count"] == 0
    assert rows[0]["evidence_path"] == str(candidate_dir)
    assert rows[0]["operator_result"] == ""
    assert rows[0]["reviewer"] == ""
    assert rows[0]["reviewed_at"] == ""
