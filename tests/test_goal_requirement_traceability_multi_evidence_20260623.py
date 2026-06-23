import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "generate_goal_requirement_traceability_20260620.py"
    spec = importlib.util.spec_from_file_location(
        "generate_goal_requirement_traceability_20260620_multi_evidence",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_evidence_sources_exist_accepts_semicolon_separated_paths(tmp_path: Path) -> None:
    module = load_module()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    assert module.evidence_sources_exist(f"{first}; {second}") is True
    assert module.evidence_sources_exist(f"{first}; {tmp_path / 'missing.json'}") is False
