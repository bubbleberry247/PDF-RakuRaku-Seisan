import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "sync_unified_final_evidence_intake_20260621.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "sync_unified_final_evidence_intake_20260621",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "bundle",
        "scenario",
        "required_final_evidence",
        "hard_stops",
        "current_reference_evidence",
        "suggested_final_evidence_folder",
        "final_evidence_path",
        "required_update_fields",
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
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def make_intake_row(bundle: str, scenario: str) -> dict[str, str]:
    return {
        "bundle": bundle,
        "scenario": scenario,
        "required_final_evidence": "log and amount summary",
        "hard_stops": "no production write",
        "current_reference_evidence": "C:\\reference.txt",
        "suggested_final_evidence_folder": f"C:\\final\\scenario_{scenario}",
        "final_evidence_path": "",
        "required_update_fields": "final_evidence_path, operator_result, reviewer, reviewed_at",
        "operator_result": "",
        "reviewer": "",
        "reviewed_at": "",
        "rakuraku_customer_login_used": "",
        "temporary_save_created": "",
        "created_data_cleanup_status": "",
        "created_data_cleanup_evidence_path": "",
        "cleanup_reviewer": "",
        "cleanup_reviewed_at": "",
        "notes": "",
    }


def write_pack_json(tmp_path: Path, intakes: list[tuple[str, str, Path]]) -> Path:
    packs = []
    for bundle, scenarios, intake_path in intakes:
        packs.append(
            {
                "bundle": bundle,
                "scenarios": scenarios,
                "scenario_count": len(scenarios.split(",")),
                "intake_path": str(intake_path),
                "final_evidence_dir": str(intake_path.parent / "final_evidence"),
                "hard_stops": "no production write",
            }
        )
    pack_json = tmp_path / "bundle_evidence_packs.json"
    pack_json.write_text(json.dumps({"packs": packs}, ensure_ascii=False), encoding="utf-8")
    return pack_json


def test_unified_input_syncs_nonblank_operator_fields(tmp_path: Path) -> None:
    module = load_module()
    intake_path = tmp_path / "business_review_bundle" / "final_evidence_intake.csv"
    write_csv(intake_path, [make_intake_row("BUSINESS_REVIEW_BUNDLE", "44")])
    pack_json = write_pack_json(
        tmp_path,
        [("BUSINESS_REVIEW_BUNDLE", "44", intake_path)],
    )
    input_csv = tmp_path / "out" / "unified_final_evidence_input.csv"
    write_csv(
        input_csv,
        [
            {
                **make_intake_row("BUSINESS_REVIEW_BUNDLE", "44"),
                "entry_key": "BUSINESS_REVIEW_BUNDLE::44",
                "final_evidence_path": str(tmp_path / "final" / "scenario_44"),
                "operator_result": "OK",
                "reviewer": "reviewer-a",
                "reviewed_at": "2026-06-21T23:00:00",
                "source_intake_path": str(intake_path),
            }
        ],
    )

    payload = module.build_payload(pack_json, input_csv, apply_updates=True)

    rows = read_csv(intake_path)
    assert payload["updated_intake_count"] == 1
    assert rows[0]["final_evidence_path"].endswith("scenario_44")
    assert rows[0]["operator_result"] == "OK"
    assert rows[0]["reviewer"] == "reviewer-a"
    assert rows[0]["reviewed_at"] == "2026-06-21T23:00:00"
    assert "synced_from_unified_final_evidence_input_20260621" in rows[0]["notes"]


def test_merge_notes_deduplicates_existing_and_incoming_parts() -> None:
    module = load_module()

    merged = module.merge_notes("alpha / beta / alpha", "beta / gamma")

    assert merged == "alpha / beta / gamma"


def test_unified_input_sync_deduplicates_note_parts_without_growth(tmp_path: Path) -> None:
    module = load_module()
    intake_path = tmp_path / "outlook_com_bundle" / "final_evidence_intake.csv"
    repeated_notes = "alpha / beta / alpha / synced_from_unified_final_evidence_input_20260621"
    write_csv(
        intake_path,
        [
            {
                **make_intake_row("OUTLOOK_COM_BUNDLE", "12/13"),
                "final_evidence_path": str(tmp_path / "final" / "scenario_12_13"),
                "notes": repeated_notes,
            }
        ],
    )
    pack_json = write_pack_json(tmp_path, [("OUTLOOK_COM_BUNDLE", "12/13", intake_path)])
    input_csv = tmp_path / "out" / "unified_final_evidence_input.csv"
    write_csv(
        input_csv,
        [
            {
                **make_intake_row("OUTLOOK_COM_BUNDLE", "12/13"),
                "entry_key": "OUTLOOK_COM_BUNDLE::12/13",
                "final_evidence_path": str(tmp_path / "final" / "scenario_12_13"),
                "notes": repeated_notes,
                "source_intake_path": str(intake_path),
            }
        ],
    )

    first_payload = module.build_payload(pack_json, input_csv, apply_updates=True)
    second_payload = module.build_payload(pack_json, input_csv, apply_updates=True)

    rows = read_csv(intake_path)
    assert rows[0]["notes"] == "alpha / beta / synced_from_unified_final_evidence_input_20260621"
    assert first_payload["updated_intake_count"] == 1
    assert second_payload["updated_intake_count"] == 0


def test_unified_input_blank_cells_do_not_clear_existing_intake_values(tmp_path: Path) -> None:
    module = load_module()
    intake_path = tmp_path / "outlook_com_bundle" / "final_evidence_intake.csv"
    existing_row = {
        **make_intake_row("OUTLOOK_COM_BUNDLE", "12/13"),
        "final_evidence_path": str(tmp_path / "final" / "scenario_12_13"),
        "operator_result": "OK",
        "reviewer": "collector",
        "reviewed_at": "2026-06-21T22:00:00",
    }
    write_csv(intake_path, [existing_row])
    pack_json = write_pack_json(tmp_path, [("OUTLOOK_COM_BUNDLE", "12/13", intake_path)])
    input_csv = tmp_path / "out" / "unified_final_evidence_input.csv"
    write_csv(
        input_csv,
        [
            {
                **make_intake_row("OUTLOOK_COM_BUNDLE", "12/13"),
                "entry_key": "OUTLOOK_COM_BUNDLE::12/13",
                "source_intake_path": str(intake_path),
            }
        ],
    )

    payload = module.build_payload(pack_json, input_csv, apply_updates=True)

    rows = read_csv(intake_path)
    assert payload["updated_intake_count"] == 0
    assert rows[0]["operator_result"] == "OK"
    assert rows[0]["reviewer"] == "collector"
    assert rows[0]["reviewed_at"] == "2026-06-21T22:00:00"


def test_unified_input_clears_legacy_outlook_auto_approval(
    tmp_path: Path,
) -> None:
    module = load_module()
    intake_path = tmp_path / "outlook_com_bundle" / "final_evidence_intake.csv"
    existing_row = {
        **make_intake_row("OUTLOOK_COM_BUNDLE", "12/13"),
        "final_evidence_path": str(tmp_path / "final" / "scenario_12_13"),
        "operator_result": "OK",
        "reviewer": "OUTLOOK_COM_BUNDLE_AUTO_COLLECTOR",
        "reviewed_at": "2026-06-22T00:13:12",
        "notes": "auto_collected_from_outlook_com_bundle_logs_20260620",
    }
    write_csv(intake_path, [existing_row])
    pack_json = write_pack_json(tmp_path, [("OUTLOOK_COM_BUNDLE", "12/13", intake_path)])
    input_csv = tmp_path / "out" / "unified_final_evidence_input.csv"
    stale_unified_row = {
        **existing_row,
        "entry_key": "OUTLOOK_COM_BUNDLE::12/13",
        "source_intake_path": str(intake_path),
    }
    write_csv(input_csv, [stale_unified_row])

    payload = module.build_payload(pack_json, input_csv, apply_updates=True)
    module.write_outputs(payload, tmp_path / "out")

    rows = read_csv(intake_path)
    unified_rows = read_csv(input_csv)
    assert payload["updated_intake_count"] == 1
    assert rows[0]["operator_result"] == ""
    assert rows[0]["reviewer"] == ""
    assert rows[0]["reviewed_at"] == ""
    assert module.LEGACY_OUTLOOK_CLEAR_NOTE in rows[0]["notes"]
    assert unified_rows[0]["operator_result"] == ""
    assert unified_rows[0]["reviewer"] == ""
    assert unified_rows[0]["reviewed_at"] == ""


def test_unified_input_does_not_overwrite_nonblank_source_with_stale_existing_csv(
    tmp_path: Path,
) -> None:
    module = load_module()
    intake_path = tmp_path / "outlook_com_bundle" / "final_evidence_intake.csv"
    source_row = {
        **make_intake_row("OUTLOOK_COM_BUNDLE", "12/13"),
        "final_evidence_path": str(tmp_path / "final" / "scenario_12_13"),
        "operator_result": "OK",
        "reviewer": "fresh-collector",
        "reviewed_at": "2026-06-21T22:56:00",
    }
    write_csv(intake_path, [source_row])
    pack_json = write_pack_json(tmp_path, [("OUTLOOK_COM_BUNDLE", "12/13", intake_path)])
    input_csv = tmp_path / "out" / "unified_final_evidence_input.csv"
    stale_row = {
        **make_intake_row("OUTLOOK_COM_BUNDLE", "12/13"),
        "entry_key": "OUTLOOK_COM_BUNDLE::12/13",
        "final_evidence_path": str(tmp_path / "old" / "scenario_12_13"),
        "operator_result": "OK",
        "reviewer": "old-collector",
        "reviewed_at": "2026-06-21T22:48:00",
        "source_intake_path": str(intake_path),
    }
    write_csv(input_csv, [stale_row])

    payload = module.build_payload(pack_json, input_csv, apply_updates=True)
    module.write_outputs(payload, tmp_path / "out")

    rows = read_csv(intake_path)
    unified_rows = read_csv(input_csv)
    assert payload["updated_intake_count"] == 0
    assert rows[0]["reviewer"] == "fresh-collector"
    assert rows[0]["reviewed_at"] == "2026-06-21T22:56:00"
    assert unified_rows[0]["reviewer"] == "fresh-collector"
    assert unified_rows[0]["reviewed_at"] == "2026-06-21T22:56:00"


def test_write_outputs_creates_unified_csv_report_and_numbered_copies(tmp_path: Path) -> None:
    module = load_module()
    intake_path = tmp_path / "payment_bundle" / "final_evidence_intake.csv"
    write_csv(intake_path, [make_intake_row("PAYMENT_APPROVAL_BUNDLE", "70")])
    pack_json = write_pack_json(tmp_path, [("PAYMENT_APPROVAL_BUNDLE", "70", intake_path)])
    input_csv = tmp_path / "out" / "unified_final_evidence_input.csv"

    payload = module.build_payload(pack_json, input_csv, apply_updates=False)
    module.write_outputs(payload, tmp_path / "out")

    assert input_csv.exists()
    assert (tmp_path / "out" / "unified_final_evidence_intake_sync.json").exists()
    assert (tmp_path / "out" / "unified_final_evidence_intake_sync.md").exists()
    assert Path(str(input_csv) + ".numbered").exists()
    assert (tmp_path / "out" / "unified_final_evidence_intake_sync.md.numbered").exists()
    assert "PAYMENT_APPROVAL_BUNDLE" in input_csv.read_text(encoding="utf-8-sig")
