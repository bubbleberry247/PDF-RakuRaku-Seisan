from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "generate_final_evidence_fill_queue_20260621.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "generate_final_evidence_fill_queue_20260621",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rk10_gate_matrix_remaining_includes_open_probe_status() -> None:
    module = load_module()

    result = module.rk10_gate_matrix_remaining(
        {
            "rows": [
                {
                    "scenario": "38",
                    "current_rks_status": "PRIMARY_RKS_EDITOR_OPEN_NG",
                    "missing_gate": "RK10 build/runtime/latest clean log",
                    "editor_open_probe_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "editor_open_probe_build_artifact_found": False,
                }
            ]
        },
        {"38"},
    )

    assert "open_probe:RK10_EDITOR_OPEN_CONFIRMED" in result
    assert "build_artifact=NO" in result
    assert "RK10 build/runtime/latest clean log" in result


def test_default_rks_matrix_uses_open_probe_report() -> None:
    module = load_module()

    assert "rks_gate_matrix_open_probe_20260622" in str(
        module.DEFAULT_RKS_GATE_MATRIX_JSON
    )
