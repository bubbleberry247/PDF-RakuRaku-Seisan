import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "backup_goal_code_artifacts_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("backup_goal_code_artifacts_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_runner(path: Path, tool_path: Path, test_path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"CHECK_SAMPLE = Path({str(tool_path)!r})",
                f"TEST_SAMPLE = Path({str(test_path)!r})",
                "OTHER_VALUE = 'ignored'",
            ]
        ),
        encoding="utf-8",
    )


def test_build_payload_copies_runner_artifacts(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    tool_path = tmp_path / "tools" / "sample_tool.py"
    test_path = tmp_path / "tests" / "test_sample_tool.py"
    runner_path = tmp_path / "runner.py"
    tool_path.parent.mkdir()
    test_path.parent.mkdir()
    tool_path.write_text("print('tool')\n", encoding="utf-8")
    test_path.write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    write_runner(runner_path, tool_path, test_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "RUNNER_PATH", runner_path)

    payload = module.build_payload(tmp_path / "out", "snapshot")

    assert payload["backup_complete"] is True
    assert payload["artifact_count"] == 2
    assert payload["tool_count"] == 1
    assert payload["test_count"] == 1
    assert Path(payload["artifacts"][0]["backup_path"]).exists()
    assert payload["artifacts"][0]["sha256"]


def test_build_payload_reports_missing_artifacts(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    tool_path = tmp_path / "tools" / "missing_tool.py"
    test_path = tmp_path / "tests" / "missing_test.py"
    runner_path = tmp_path / "runner.py"
    write_runner(runner_path, tool_path, test_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "RUNNER_PATH", runner_path)

    payload = module.build_payload(tmp_path / "out", "snapshot")

    assert payload["backup_complete"] is False
    assert payload["missing_count"] == 2
    assert payload["artifacts"][0]["source_exists"] is False


def test_write_outputs_creates_manifest_and_numbered_markdown(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    tool_path = tmp_path / "tools" / "sample_tool.py"
    test_path = tmp_path / "tests" / "test_sample_tool.py"
    runner_path = tmp_path / "runner.py"
    tool_path.parent.mkdir()
    test_path.parent.mkdir()
    tool_path.write_text("print('tool')\n", encoding="utf-8")
    test_path.write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    write_runner(runner_path, tool_path, test_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "RUNNER_PATH", runner_path)
    out_dir = tmp_path / "out"
    payload = module.build_payload(out_dir, "snapshot")

    module.write_outputs(payload, out_dir)

    json_path = out_dir / "goal_code_artifact_backups.json"
    assert json.loads(json_path.read_text(encoding="utf-8"))["artifact_count"] == 2
    assert (out_dir / "goal_code_artifact_backups.md.numbered").exists()
