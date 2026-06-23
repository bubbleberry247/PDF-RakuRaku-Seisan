import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "sync_rks_runtime_evidence_from_status_gates_20260620.py"
    spec = importlib.util.spec_from_file_location("sync_rks_runtime_evidence_from_status_gates_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_status_gate(path: Path, rks_path: str, final_status: str = "OK_FOR_SAFE_STOP_TEST") -> None:
    path.write_text(
        "\n".join(
            [
                "# RK10 RKS Status Gate",
                "",
                "Created: 2026-06-18T10:18:53",
                f"File: `{rks_path}`",
                f"Final status: `{final_status}`",
                "Reason: safe-stop evidence provided",
                "",
                "## Evidence",
                "",
                "- Static guard: `OK_CANDIDATE`",
                "- RK10 editor open: `confirmed`",
                "- RK10 build: `confirmed`",
                "- Runtime / safe-stop: `confirmed`",
                "- Latest log: `clean`",
                "- Scope: `safe-stop`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_partial_open_build_tsv(path: Path, scenario: str, rks_path: str) -> None:
    path.write_text(
        "\n".join(
            [
                "scenario\tguard_rc\teditor_status\tlicense_action\tbuild_artifact_found\tstatus_gate_rc\tafter_process_count\trks",
                f"{scenario}\t0\tRK10_EDITOR_OPEN_CONFIRMED\tok_invoked\tTrue\t1\t0\t{rks_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_static_audit(path: Path, status_gate: Path, rks_path: str) -> None:
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "scenario": "37",
                        "rks_path": rks_path,
                        "existing_status_gate_status": "OK_FOR_SAFE_STOP_TEST",
                        "existing_status_gate_evidence": str(status_gate),
                    },
                    {
                        "scenario": "57",
                        "rks_path": r"C:\RK10\57.rks",
                        "existing_status_gate_status": "",
                        "existing_status_gate_evidence": "",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_intake(path: Path, rows: list[dict[str, str]]) -> None:
    module = load_module()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_intake(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_payload_imports_only_complete_status_gate_into_blank_intakes(tmp_path: Path) -> None:
    module = load_module()
    rks_path = r"C:\RK10\37.rks"
    status_gate = tmp_path / "s37.status_gate.md.numbered"
    audit = tmp_path / "audit.json"
    out_intake = tmp_path / "out" / "rks_runtime_operator_intake.csv"
    bundle_intake = tmp_path / "bundle" / "rks_runtime_operator_intake.csv"
    write_status_gate(status_gate, rks_path)
    write_static_audit(audit, status_gate, rks_path)
    rows = [
        {"scenario": "37", "rks_path": rks_path},
        {"scenario": "57", "rks_path": r"C:\RK10\57.rks"},
    ]
    write_intake(out_intake, rows)
    write_intake(bundle_intake, rows)

    payload = module.build_payload(audit, out_intake, bundle_intake)

    assert payload["candidate_status_gate_count"] == 1
    assert payload["importable_status_gate_count"] == 1
    assert payload["updated_intake_count"] == 2
    out_rows = read_intake(out_intake)
    assert out_rows[0]["operator_decision"] == "SAFE_STOP_ONLY"
    assert out_rows[0]["rk10_editor_open"] == "CONFIRMED"
    assert out_rows[0]["latest_log_clean"] == "YES"
    assert out_rows[0]["latest_log_path"] == str(status_gate)
    assert out_rows[1]["operator_decision"] == ""


def test_build_payload_does_not_overwrite_manual_operator_input(tmp_path: Path) -> None:
    module = load_module()
    rks_path = r"C:\RK10\37.rks"
    status_gate = tmp_path / "s37.status_gate.md.numbered"
    audit = tmp_path / "audit.json"
    out_intake = tmp_path / "out" / "rks_runtime_operator_intake.csv"
    bundle_intake = tmp_path / "bundle" / "rks_runtime_operator_intake.csv"
    write_status_gate(status_gate, rks_path)
    write_static_audit(audit, status_gate, rks_path)
    manual_rows = [
        {
            "scenario": "37",
            "rks_path": rks_path,
            "operator_decision": "REGENERATE_SAVE_AS_REQUIRED",
            "notes": "manual decision",
        }
    ]
    write_intake(out_intake, manual_rows)
    write_intake(bundle_intake, manual_rows)

    payload = module.build_payload(audit, out_intake, bundle_intake)

    assert payload["updated_intake_count"] == 0
    assert payload["preserved_manual_count"] == 2
    assert read_intake(out_intake)[0]["operator_decision"] == "REGENERATE_SAVE_AS_REQUIRED"
    assert read_intake(out_intake)[0]["notes"] == "manual decision"


def test_build_payload_rejects_status_gate_without_clean_latest_log(tmp_path: Path) -> None:
    module = load_module()
    rks_path = r"C:\RK10\37.rks"
    status_gate = tmp_path / "s37.status_gate.md.numbered"
    audit = tmp_path / "audit.json"
    out_intake = tmp_path / "out" / "rks_runtime_operator_intake.csv"
    bundle_intake = tmp_path / "bundle" / "rks_runtime_operator_intake.csv"
    write_status_gate(status_gate, rks_path)
    text = status_gate.read_text(encoding="utf-8").replace("- Latest log: `clean`", "- Latest log: `none`")
    status_gate.write_text(text, encoding="utf-8")
    write_static_audit(audit, status_gate, rks_path)
    write_intake(out_intake, [{"scenario": "37", "rks_path": rks_path}])
    write_intake(bundle_intake, [{"scenario": "37", "rks_path": rks_path}])

    payload = module.build_payload(audit, out_intake, bundle_intake)

    assert payload["candidate_status_gate_count"] == 1
    assert payload["importable_status_gate_count"] == 0
    assert payload["updated_intake_count"] == 0
    assert payload["evidence_rows"][0]["reason"] == "STATUS_GATE_NOT_STRONG_ENOUGH"


def test_build_payload_imports_partial_open_build_without_approving_runtime(
    tmp_path: Path,
) -> None:
    module = load_module()
    rks_path = r"C:\RK10\57.rks"
    audit = tmp_path / "audit.json"
    out_intake = tmp_path / "out" / "rks_runtime_operator_intake.csv"
    bundle_intake = tmp_path / "bundle" / "rks_runtime_operator_intake.csv"
    partial_tsv = tmp_path / "summary.tsv"
    audit.write_text(json.dumps({"rows": []}, ensure_ascii=False), encoding="utf-8")
    write_partial_open_build_tsv(partial_tsv, "57", rks_path)
    write_intake(out_intake, [{"scenario": "57", "rks_path": rks_path}])
    write_intake(bundle_intake, [{"scenario": "57", "rks_path": rks_path}])

    payload = module.build_payload(
        audit,
        out_intake,
        bundle_intake,
        partial_open_build_tsvs=(partial_tsv,),
    )

    assert payload["importable_status_gate_count"] == 0
    assert payload["importable_partial_open_build_count"] == 1
    assert payload["partial_updated_intake_count"] == 2
    out_row = read_intake(out_intake)[0]
    assert out_row["rk10_editor_open"] == "CONFIRMED"
    assert out_row["rk10_build"] == "CONFIRMED"
    assert out_row["operator_decision"] == ""
    assert out_row["runtime_or_safe_stop"] == ""
    assert out_row["latest_log_clean"] == ""
    assert out_row["latest_log_path"] == ""
    assert "Runtime/safe-stop and latest clean log still required" in out_row["notes"]


def test_build_markdown_documents_safe_stop_scope() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "overall_goal_complete": False,
        "safety": "read-only",
        "static_audit_json": "audit.json",
        "candidate_status_gate_count": 1,
        "importable_status_gate_count": 1,
        "candidate_partial_open_build_count": 0,
        "importable_partial_open_build_count": 0,
        "updated_intake_count": 1,
        "partial_updated_intake_count": 0,
        "preserved_manual_count": 0,
        "evidence_rows": [
            {
                "scenario": "37",
                "importable": True,
                "final_status": "OK_FOR_SAFE_STOP_TEST",
                "scope": "safe-stop",
                "reason": "IMPORTABLE",
                "status_gate_path": "gate.md",
            }
        ],
        "partial_open_build_rows": [],
        "sync_results": [
            {
                "intake_csv": "intake.csv",
                "intake_exists": True,
                "row_count": 1,
                "updated_count": 1,
                "partial_updated_count": 0,
                "preserved_manual_count": 0,
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "safe-stop evidence only" in markdown
    assert "Existing manual operator input is never overwritten" in markdown
    assert "Partial open/build evidence may fill only RK10 editor open/build" in markdown
    assert "OK_FOR_SAFE_STOP_TEST" in markdown
