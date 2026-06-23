import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "run_rks_editor_open_build_probe_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "run_rks_editor_open_build_probe_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_focus_csv(path: Path, rks_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scenario",
                "status",
                "rks_path",
                "required_next_gate",
                "blocked_operations",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "scenario": "58",
                "status": "WAITING_OPERATOR_RK10_EVIDENCE",
                "rks_path": str(rks_path),
                "required_next_gate": "operator-select, no-mail/no-write runtime evidence",
                "blocked_operations": "MainSV本番TXT書込; 保存通知メール送信; RK10 ButtonRun",
            }
        )


def test_read_focus_targets_filters_scenario(tmp_path: Path) -> None:
    module = load_module()
    rks_path = tmp_path / "58.rks"
    rks_path.write_text("fake", encoding="utf-8")
    focus_csv = tmp_path / "focus.csv"
    write_focus_csv(focus_csv, rks_path)

    targets = module.read_focus_targets(focus_csv, {"58"})

    assert len(targets) == 1
    assert targets[0].scenario == "58"
    assert targets[0].expected_name == "58.rks"
    assert "ButtonRun" in targets[0].blocked_operations


def test_plan_only_payload_never_executes_gui(tmp_path: Path) -> None:
    module = load_module()
    rks_path = tmp_path / "58.rks"
    rks_path.write_text("fake", encoding="utf-8")
    target = module.ProbeTarget(
        scenario="58",
        rks_path=str(rks_path),
        expected_name="58.rks",
        required_next_gate="open build",
        blocked_operations="ButtonRun",
    )

    row = module.build_plan_row(
        target,
        tmp_path / "RkScenarioManager.exe",
        tmp_path / "out",
        "startfile",
    )
    payload = module.build_payload([row], execute_gui=False, out_dir=tmp_path / "out")

    assert row.executed is False
    assert row.button_run_clicked is False
    assert row.launch_mode == "startfile"
    assert row.license_action == "PLANNED"
    assert row.home_load_action == "PLANNED"
    assert row.editor_open_status == "PLANNED_NOT_EXECUTED"
    assert payload["button_run_clicked_count"] == 0
    assert payload["editor_confirmed_count"] == 0


def test_write_outputs_creates_numbered_markdown(tmp_path: Path) -> None:
    module = load_module()
    row = module.ProbeRow(
        scenario="58",
        rks_path=r"C:\RK10\58.rks",
        planned=True,
        executed=False,
        rks_exists=True,
        rk10_exe_exists=True,
        launch_mode="startfile",
        metadata_guard_returncode=None,
        license_action="PLANNED",
        home_load_action="PLANNED",
        editor_open_status="PLANNED_NOT_EXECUTED",
        build_artifact_found=False,
        debugger_program_match_count=0,
        button_run_clicked=False,
        new_process_ids="",
        stopped_process_ids="",
        top_window_titles="",
        top_window_details_path="",
        error="",
        evidence_path=str(tmp_path / "out"),
    )
    payload = module.build_payload([row], execute_gui=False, out_dir=tmp_path / "out")

    module.write_outputs(payload, tmp_path / "out")

    md_path = tmp_path / "out" / "rks_editor_open_build_probe.md"
    assert (tmp_path / "out" / "rks_editor_open_build_probe.json").exists()
    assert md_path.exists()
    assert Path(str(md_path) + ".numbered").exists()
    markdown = md_path.read_text(encoding="utf-8")
    assert "ButtonRun Clicked" in markdown
    assert "Home Load" in markdown
    assert "UI Details" in markdown
    assert "PLANNED_NOT_EXECUTED" in markdown
