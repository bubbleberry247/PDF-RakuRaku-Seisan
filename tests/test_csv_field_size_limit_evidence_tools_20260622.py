import csv
import importlib.util
import sys
from pathlib import Path


MODULE_NAMES = [
    "generate_bundle_evidence_packs_20260620",
    "collect_rk10_runtime_bundle_evidence_20260620",
    "collect_outlook_bundle_evidence_20260620",
    "stage_final_evidence_candidates_20260621",
    "sync_unified_final_evidence_intake_20260621",
    "sync_execution_packet_candidate_evidence_paths_20260621",
    "sync_bundle_evidence_intake_20260620",
]


def load_tool_module(module_name: str):
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / f"{module_name}.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_evidence_csv_tools_raise_csv_field_size_limit() -> None:
    for module_name in MODULE_NAMES:
        module = load_tool_module(module_name)

        assert module.CSV_FIELD_SIZE_LIMIT > 200_000
        assert csv.field_size_limit() > 200_000
