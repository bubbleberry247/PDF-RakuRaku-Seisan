import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "run_rks_editor_open_build_probe_20260620_safe_exe_default_20260622.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "run_rks_editor_open_build_probe_20260620_safe_exe_default_20260622",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_safe_file_token_replaces_path_separators() -> None:
    module = load_module()

    assert module.safe_file_token("51/52") == "51_52"
    assert module.safe_file_token(r"12\13") == "12_13"


def test_write_top_window_details_uses_safe_scenario_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    target = module.ProbeTarget(
        scenario="51/52",
        rks_path=str(tmp_path / "scenario.rks"),
        expected_name="scenario.rks",
        required_next_gate="open/build",
        blocked_operations="ButtonRun",
    )

    class EmptyDesktop:
        def __init__(self, backend: str) -> None:
            self.backend = backend

        def windows(self) -> list[object]:
            return []

    monkeypatch.setitem(sys.modules, "pywinauto", type("PyWinAuto", (), {"Desktop": EmptyDesktop}))

    detail_path = module.write_top_window_details(tmp_path, target, set())

    assert detail_path.endswith("s51_52_top_window_details.json")
    assert Path(detail_path).exists()
