import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "validate_bundle_evidence_packs_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("validate_bundle_evidence_packs_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_pack_files(root: Path, bundle: str, source: Path) -> dict[str, object]:
    pack_dir = root / bundle.lower()
    pack_dir.mkdir(parents=True)
    manifest_path = pack_dir / "evidence_manifest.json"
    checklist_path = pack_dir / "operator_evidence_checklist.md"
    intake_path = pack_dir / "final_evidence_intake.csv"
    filename_template_path = pack_dir / "operator_evidence_filename_template.csv"
    filename_template_markdown_path = pack_dir / "operator_evidence_filename_template.md"
    final_evidence_dir = pack_dir / "final_evidence"
    final_evidence_dir.mkdir()
    manifest_payload = {
        "bundle": bundle,
        "scenarios": "44",
        "scenario_count": 1,
    }
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    checklist_path.write_text(
        "\n".join(
            [
                "# Checklist",
                "- Do not use this pack alone as approval; it is only a prepared evidence container.",
            ]
        ),
        encoding="utf-8",
    )
    Path(str(checklist_path) + ".numbered").write_text("    1: # Checklist\n", encoding="utf-8")
    intake_path.write_text(
        "bundle,scenario,final_evidence_path,operator_result,reviewer,reviewed_at,notes\n",
        encoding="utf-8-sig",
    )
    filename_template_path.write_text(
        "\n".join(
            [
                "bundle,scenario,template_only_not_final_evidence,save_under_folder,evidence_kind,example_filename,purpose,notes",
                f"{bundle},44,YES,{final_evidence_dir / 'scenario_44'},log,scenario_44_safe_run_log_YYYYMMDD_HHMMSS.txt,Safe run log,Template only",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )
    filename_template_markdown_path.write_text(
        "\n".join(
            [
                "# Template",
                "- scope: `TEMPLATE_ONLY_NOT_FINAL_EVIDENCE`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    Path(str(filename_template_markdown_path) + ".numbered").write_text(
        "    1: # Template\n",
        encoding="utf-8",
    )
    return {
        "bundle": bundle,
        "scenarios": "44",
        "scenario_count": 1,
        "pack_dir": str(pack_dir),
        "manifest_path": str(manifest_path),
        "checklist_path": str(checklist_path),
        "intake_path": str(intake_path),
        "filename_template_path": str(filename_template_path),
        "filename_template_markdown_path": str(filename_template_markdown_path),
        "final_evidence_dir": str(final_evidence_dir),
        "scenario_evidence": [
            {
                "scenario": "44",
                "source": str(source),
                "source_exists": True,
                "current_reference_evidence": str(source),
                "current_reference_exists": True,
            }
        ],
    }


def write_bundle_json(path: Path, packs: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"packs": packs}, ensure_ascii=False),
        encoding="utf-8",
    )


def write_operator_sheet(path: Path, bundle: str, evidence_path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["bundle", "operator_result", "evidence_path", "reviewer", "reviewed_at"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "bundle": bundle,
                "operator_result": "OK",
                "evidence_path": str(evidence_path),
                "reviewer": "tester",
                "reviewed_at": "2026-06-20T12:00:00",
            }
        )


def write_blank_operator_sheet(path: Path, bundle: str) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["bundle", "operator_result", "evidence_path", "reviewer", "reviewed_at"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "bundle": bundle,
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )


def write_intake_sync_json(
    path: Path,
    bundle: str,
    final_evidence_dir: Path,
    final_evidence_path: Path,
) -> None:
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "bundle": bundle,
                        "final_evidence_dir": str(final_evidence_dir),
                        "rows": [
                            {
                                "scenario": "44",
                                "final_evidence_path": str(final_evidence_path),
                                "final_evidence_exists": True,
                                "final_evidence_has_content": True,
                                "final_evidence_under_final_dir": True,
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_build_payload_validates_prepared_pack_and_final_evidence(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    final_evidence = tmp_path / "final"
    final_evidence.mkdir()
    (final_evidence / "scenario_44_safe_run_log_20260620_120000.txt").write_text("completed", encoding="utf-8")
    bundle = "BUSINESS_REVIEW_BUNDLE"
    pack_json = tmp_path / "bundle_evidence_packs.json"
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    write_bundle_json(pack_json, [write_pack_files(tmp_path / "packs", bundle, source)])
    write_operator_sheet(operator_sheet, bundle, final_evidence)

    payload = module.build_payload(pack_json, operator_sheet)

    assert payload["prepared_pack_validation_passed"] is True
    assert payload["final_evidence_complete"] is True
    assert payload["prepared_pack_ready_count"] == 1
    assert payload["final_evidence_ready_count"] == 1
    assert payload["source_reference_exists_now_count"] == 1
    assert payload["source_reference_hashed_now_count"] == 1
    assert payload["checks"][0]["final_evidence_item_count"] == 1
    assert payload["checks"][0]["final_evidence_has_content"] is True
    assert payload["checks"][0]["final_evidence_filenames_match"] is True
    assert payload["checks"][0]["final_evidence_filename_mismatch_count"] == 0
    reference = payload["checks"][0]["scenario_references"][0]
    assert reference["source_size_bytes"] == 2
    assert reference["source_sha256"] == hashlib.sha256(b"ok").hexdigest()
    assert reference["current_reference_size_bytes"] == 2
    assert reference["current_reference_sha256"] == hashlib.sha256(b"ok").hexdigest()


def test_build_payload_uses_intake_sync_path_without_approving_operator_fields(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    bundle = "BUSINESS_REVIEW_BUNDLE"
    pack = write_pack_files(tmp_path / "packs", bundle, source)
    final_evidence_dir = Path(str(pack["final_evidence_dir"]))
    final_scenario_dir = final_evidence_dir / "scenario_44"
    final_scenario_dir.mkdir()
    (final_scenario_dir / "scenario_44_safe_run_log_20260620_120000.txt").write_text(
        "completed",
        encoding="utf-8",
    )
    pack_json = tmp_path / "bundle_evidence_packs.json"
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    intake_sync_json = tmp_path / "bundle_evidence_intake_sync.json"
    write_bundle_json(pack_json, [pack])
    write_blank_operator_sheet(operator_sheet, bundle)
    write_intake_sync_json(intake_sync_json, bundle, final_evidence_dir, final_scenario_dir)

    payload = module.build_payload(pack_json, operator_sheet, intake_sync_json)

    check = payload["checks"][0]
    assert payload["final_evidence_complete"] is False
    assert payload["final_evidence_ready_count"] == 0
    assert check["final_evidence_path_source"] == "final_evidence_intake_sync"
    assert check["final_evidence_path"] == str(final_scenario_dir)
    assert check["final_evidence_path_exists"] is True
    assert check["final_evidence_has_content"] is True
    assert check["final_evidence_item_count"] == 1
    assert check["final_evidence_path_issue"] == ""
    assert check["final_evidence_filename_issue"] == ""
    assert check["operator_fields_complete"] is False
    assert check["operator_field_issue"] == "OPERATOR_RESULT_BLANK, REVIEWER_BLANK, REVIEWED_AT_BLANK"
    assert "EVIDENCE_PATH_BLANK" not in check["operator_field_issue"]


def test_build_payload_detects_missing_checklist_numbered_copy(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    bundle = "BUSINESS_REVIEW_BUNDLE"
    pack = write_pack_files(tmp_path / "packs", bundle, source)
    Path(str(pack["checklist_path"]) + ".numbered").unlink()
    pack_json = tmp_path / "bundle_evidence_packs.json"
    write_bundle_json(pack_json, [pack])

    payload = module.build_payload(pack_json, tmp_path / "missing_sheet.csv")

    assert payload["prepared_pack_validation_passed"] is False
    assert payload["missing_prepared_pack_count"] == 1
    assert payload["checks"][0]["prepared_pack_ready"] is False
    assert payload["checks"][0]["numbered_checklist_exists"] is False


def test_build_payload_rejects_empty_final_evidence_folder(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    empty_final_evidence = tmp_path / "empty_final"
    empty_final_evidence.mkdir()
    bundle = "BUSINESS_REVIEW_BUNDLE"
    pack_json = tmp_path / "bundle_evidence_packs.json"
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    write_bundle_json(pack_json, [write_pack_files(tmp_path / "packs", bundle, source)])
    write_operator_sheet(operator_sheet, bundle, empty_final_evidence)

    payload = module.build_payload(pack_json, operator_sheet)

    assert payload["prepared_pack_validation_passed"] is True
    assert payload["final_evidence_complete"] is False
    assert payload["final_evidence_ready_count"] == 0
    assert payload["checks"][0]["final_evidence_path_exists"] is True
    assert payload["checks"][0]["final_evidence_has_content"] is False
    assert payload["checks"][0]["final_evidence_filename_issue"] == "NO_FINAL_EVIDENCE_FILES"


def test_build_payload_rejects_final_evidence_with_only_empty_scenario_subfolder(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    bundle = "BUSINESS_REVIEW_BUNDLE"
    pack = write_pack_files(tmp_path / "packs", bundle, source)
    final_evidence = Path(str(pack["final_evidence_dir"]))
    (final_evidence / "scenario_44").mkdir()
    pack_json = tmp_path / "bundle_evidence_packs.json"
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    write_bundle_json(pack_json, [pack])
    write_operator_sheet(operator_sheet, bundle, final_evidence)

    payload = module.build_payload(pack_json, operator_sheet)

    assert payload["prepared_pack_validation_passed"] is True
    assert payload["final_evidence_complete"] is False
    assert payload["final_evidence_ready_count"] == 0
    assert payload["checks"][0]["final_evidence_item_count"] == 0


def test_build_payload_rejects_prepared_pack_root_as_final_evidence(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    bundle = "BUSINESS_REVIEW_BUNDLE"
    pack_json = tmp_path / "bundle_evidence_packs.json"
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    pack = write_pack_files(tmp_path / "packs", bundle, source)
    write_bundle_json(pack_json, [pack])
    write_operator_sheet(operator_sheet, bundle, Path(str(pack["pack_dir"])))

    payload = module.build_payload(pack_json, operator_sheet)

    assert payload["prepared_pack_validation_passed"] is True
    assert payload["final_evidence_complete"] is False
    assert payload["final_evidence_ready_count"] == 0
    assert payload["checks"][0]["final_evidence_path_exists"] is True
    assert payload["checks"][0]["final_evidence_path_allowed"] is False
    assert payload["checks"][0]["final_evidence_path_issue"] == "PREPARED_PACK_ROOT_IS_NOT_FINAL_EVIDENCE"


def test_build_payload_rejects_final_evidence_filename_mismatch(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    final_evidence = tmp_path / "final"
    final_evidence.mkdir()
    (final_evidence / "run_log.txt").write_text("completed", encoding="utf-8")
    bundle = "BUSINESS_REVIEW_BUNDLE"
    pack_json = tmp_path / "bundle_evidence_packs.json"
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    write_bundle_json(pack_json, [write_pack_files(tmp_path / "packs", bundle, source)])
    write_operator_sheet(operator_sheet, bundle, final_evidence)

    payload = module.build_payload(pack_json, operator_sheet)

    assert payload["prepared_pack_validation_passed"] is True
    assert payload["final_evidence_complete"] is False
    assert payload["final_evidence_ready_count"] == 0
    assert payload["checks"][0]["final_evidence_filename_match_count"] == 0
    assert payload["checks"][0]["final_evidence_filename_mismatch_count"] == 1
    assert payload["checks"][0]["final_evidence_filename_issue"] == "FILENAME_TEMPLATE_MISMATCH"
    assert payload["checks"][0]["final_evidence_filename_mismatches"] == "run_log.txt"


def test_build_payload_detects_missing_filename_template(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    bundle = "BUSINESS_REVIEW_BUNDLE"
    pack = write_pack_files(tmp_path / "packs", bundle, source)
    Path(str(pack["filename_template_path"])).unlink()
    pack_json = tmp_path / "bundle_evidence_packs.json"
    write_bundle_json(pack_json, [pack])

    payload = module.build_payload(pack_json, tmp_path / "missing_sheet.csv")

    assert payload["prepared_pack_validation_passed"] is False
    assert payload["missing_prepared_pack_count"] == 1
    assert payload["checks"][0]["prepared_pack_ready"] is False
    assert payload["checks"][0]["filename_template_exists"] is False


def test_build_markdown_states_not_production_approval(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.md"
    source.write_text("ok", encoding="utf-8")
    pack_json = tmp_path / "bundle_evidence_packs.json"
    write_bundle_json(
        pack_json,
        [write_pack_files(tmp_path / "packs", "BUSINESS_REVIEW_BUNDLE", source)],
    )
    payload = module.build_payload(pack_json, tmp_path / "missing_sheet.csv")

    markdown = module.build_markdown(payload)

    assert "# 6束証跡パック検証 2026-06-20" in markdown
    assert "source_reference_hashed_now_count" in markdown
    assert "Evidence Path Issue" in markdown
    assert "does not approve production completion" in markdown
