import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_operator_evidence_prefill_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_operator_evidence_prefill_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_filename_template(
    tmp_path: Path,
    folder: str,
    bundle: str,
    scenario: str,
    example_filename: str,
) -> tuple[Path, Path]:
    pack_dir = tmp_path / folder
    pack_dir.mkdir(parents=True, exist_ok=True)
    template_path = pack_dir / "operator_evidence_filename_template.csv"
    template_md_path = pack_dir / "operator_evidence_filename_template.md"
    template_path.write_text(
        "\n".join(
            [
                "bundle,scenario,template_only_not_final_evidence,save_under_folder,evidence_kind,example_filename,purpose,notes",
                f"{bundle},{scenario},YES,{pack_dir / 'final_evidence'},log,{example_filename},Required final evidence name,Template only",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )
    template_md_path.write_text("# Template\n", encoding="utf-8")
    return template_path, template_md_path


def write_sample_inputs(tmp_path: Path) -> tuple[Path, Path]:
    pack_json = tmp_path / "bundle_evidence_packs.json"
    next_queue_json = tmp_path / "next_approval_queue.json"
    outlook_template, outlook_template_md = write_filename_template(
        tmp_path,
        "outlook",
        "OUTLOOK_COM_BUNDLE",
        "12/13",
        "scenario_12_13_dryrun_no_print_no_mail_YYYYMMDD_HHMMSS.log",
    )
    payment_template, payment_template_md = write_filename_template(
        tmp_path,
        "payment",
        "PAYMENT_APPROVAL_BUNDLE",
        "70",
        "scenario_70_confirm_preview_YYYYMMDD_HHMMSS.txt",
    )
    business_template, business_template_md = write_filename_template(
        tmp_path,
        "business",
        "BUSINESS_DATA_APPROVAL_BUNDLE",
        "43",
        "scenario_43_business_approval_YYYYMMDD_HHMMSS.txt",
    )
    pack_json.write_text(
        json.dumps(
            {
                "packs": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "owner": "PC/Outlook管理者",
                        "scenarios": "12/13",
                        "scenario_count": 1,
                        "intake_path": str(tmp_path / "outlook" / "final_evidence_intake.csv"),
                        "final_evidence_dir": str(tmp_path / "outlook" / "final_evidence"),
                        "filename_template_path": str(outlook_template),
                        "filename_template_markdown_path": str(outlook_template_md),
                        "reference_snapshot_path": str(tmp_path / "outlook" / "reference.csv"),
                        "required_final_evidence": "COM check exit 0、dry-runログ",
                        "scenario_evidence": [
                            {"scenario": "12/13", "current_reference_exists": True}
                        ],
                    },
                    {
                        "bundle": "PAYMENT_APPROVAL_BUNDLE",
                        "owner": "支払承認者",
                        "scenarios": "70",
                        "scenario_count": 1,
                        "intake_path": str(tmp_path / "payment" / "final_evidence_intake.csv"),
                        "final_evidence_dir": str(tmp_path / "payment" / "final_evidence"),
                        "filename_template_path": str(payment_template),
                        "filename_template_markdown_path": str(payment_template_md),
                        "reference_snapshot_path": str(tmp_path / "payment" / "reference.csv"),
                        "required_final_evidence": "preview件数/金額、execute未実行ログ",
                        "scenario_evidence": [
                            {"scenario": "70", "current_reference_exists": True}
                        ],
                    },
                    {
                        "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                        "owner": "業務担当者",
                        "scenarios": "43, 47",
                        "scenario_count": 2,
                        "intake_path": str(tmp_path / "business" / "final_evidence_intake.csv"),
                        "final_evidence_dir": str(tmp_path / "business" / "final_evidence"),
                        "filename_template_path": str(business_template),
                        "filename_template_markdown_path": str(business_template_md),
                        "reference_snapshot_path": str(tmp_path / "business" / "reference.csv"),
                        "required_final_evidence": "対象日、停止条件、承認者",
                        "scenario_evidence": [
                            {"scenario": "43", "current_reference_exists": True},
                            {"scenario": "47", "current_reference_exists": True},
                        ],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    next_queue_json.write_text(
        json.dumps(
            {
                "outlook_com_status": "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED",
                "outlook_com_diagnosis_report": str(tmp_path / "outlook_diag.md.numbered"),
                "rows": [
                    {
                        "rank": 1,
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "operator_action": "Close Outlook and rerun OUTLOOK_COM_BUNDLE.",
                        "evidence_pack_path": str(tmp_path / "outlook"),
                    },
                    {
                        "rank": 3,
                        "bundle": "PAYMENT_APPROVAL_BUNDLE",
                        "operator_action": "confirm-previewのみ実施する",
                        "evidence_pack_path": str(tmp_path / "payment"),
                    },
                    {
                        "rank": 5,
                        "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                        "operator_action": "実対象データと停止条件を決める",
                        "evidence_pack_path": str(tmp_path / "business"),
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return pack_json, next_queue_json


def test_build_rows_creates_non_approving_prefill(tmp_path: Path) -> None:
    module = load_module()
    pack_json, next_queue_json = write_sample_inputs(tmp_path)

    rows = module.build_rows(pack_json, next_queue_json)

    assert [row.bundle for row in rows] == [
        "OUTLOOK_COM_BUNDLE",
        "PAYMENT_APPROVAL_BUNDLE",
        "BUSINESS_DATA_APPROVAL_BUNDLE",
    ]
    assert rows[0].current_status == "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED"
    assert rows[0].current_blocker_evidence_path.endswith("outlook_diag.md.numbered")
    assert rows[0].proposed_operator_result == ""
    assert rows[0].can_auto_approve == "NO"
    assert rows[0].reviewer_required == "YES"
    assert rows[0].suggested_scenario_folders.endswith("final_evidence\\scenario_12_13")
    assert rows[0].filename_example_count == 1
    assert "scenario_12_13_dryrun_no_print_no_mail" in rows[0].filename_examples
    assert "outlook_com_bundle_dryrun.ps1" in rows[0].supporting_input_paths
    assert rows[1].reference_evidence_count == 1
    assert (
        "s70_payment_confirmation_gate_checklist_prefill.csv"
        in rows[1].supporting_input_paths
    )
    assert rows[2].reference_evidence_count == 2
    assert "business_data_approval_checklist.csv" in rows[2].supporting_input_paths


def test_supporting_input_paths_include_s44_priority_csvs() -> None:
    module = load_module()

    paths = module.supporting_input_paths_for_bundle("BUSINESS_REVIEW_BUNDLE")

    assert paths.split(" / ")[0].endswith("s44_business_review_single_entry_input.csv")
    assert "s44_business_review_next_steps.md" in paths
    assert "s44_business_review_decision_input.csv" in paths
    assert "s44_business_review_bucket_decision_input.csv" in paths
    assert "s44_business_review_priority_queue.csv" in paths
    assert "s44_review_01_amount_zero_review.csv" in paths
    assert "s44_review_02_amount_mismatch_review.csv" in paths
    assert "s44_review_03_amount_match_quick_review.csv" in paths
    assert "s44_business_review_aid.csv" in paths


def test_supporting_input_paths_include_s71_environment_presence() -> None:
    module = load_module()

    paths = module.supporting_input_paths_for_bundle("PAID_AZURE_OCR_BUNDLE")

    assert "s71_azure_ocr_environment_presence.csv" in paths
    assert "s71_paid_azure_one_pdf_smoke_summary_template.json" in paths


def test_build_payload_counts_no_auto_approval(tmp_path: Path) -> None:
    module = load_module()
    pack_json, next_queue_json = write_sample_inputs(tmp_path)

    payload = module.build_payload(pack_json, next_queue_json)

    assert payload["overall_goal_complete"] is False
    assert payload["row_count"] == 3
    assert payload["auto_approved_count"] == 0
    assert "draft guidance only" in payload["safety"]


def test_build_field_action_summary_points_to_folder_and_intake(tmp_path: Path) -> None:
    module = load_module()
    pack_json, next_queue_json = write_sample_inputs(tmp_path)
    payload = module.build_payload(pack_json, next_queue_json)

    actions = module.build_field_action_summary(payload["rows"])

    assert actions[0]["bundle"] == "OUTLOOK_COM_BUNDLE"
    assert actions[0]["put_final_evidence_here"].endswith(
        "final_evidence\\scenario_12_13"
    )
    assert actions[0]["then_update_this_csv"].endswith("final_evidence_intake.csv")
    assert "outlook_com_bundle_dryrun.ps1" in actions[0]["complete_these_input_files"]
    assert "scenario_12_13_dryrun_no_print_no_mail" in actions[0]["save_with_these_names"]
    assert actions[0]["filename_template"].endswith("operator_evidence_filename_template.csv")
    assert actions[0]["current_blocker"] == "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED"
    assert "Close Outlook" in actions[0]["next_action"]
    assert (
        "s70_payment_confirmation_gate_checklist_prefill.csv"
        in actions[1]["complete_these_input_files"]
    )
    assert "scenario_43" in actions[2]["put_final_evidence_here"]
    assert "scenario_47" in actions[2]["put_final_evidence_here"]


def test_build_markdown_warns_not_approval(tmp_path: Path) -> None:
    module = load_module()
    pack_json, next_queue_json = write_sample_inputs(tmp_path)
    payload = module.build_payload(pack_json, next_queue_json)

    markdown = module.build_markdown(payload)

    assert "This file is a draft helper, not approval evidence." in markdown
    assert "## Field Action Summary" in markdown
    assert "Then Update This CSV" in markdown
    assert "Complete These Input Files" in markdown
    assert "Save With These Names" in markdown
    assert "Filename Template" in markdown
    assert "business_data_approval_checklist.csv" in markdown
    assert "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED" in markdown
    assert "Auto Approve" in markdown
    assert "Suggested Scenario Folders" in markdown
    assert "scenario_12_13" in markdown
    assert "scenario_12_13_dryrun_no_print_no_mail_YYYYMMDD_HHMMSS.log" in markdown
