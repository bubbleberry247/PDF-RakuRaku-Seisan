import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "run_safe_goal_checks_20260620_ai_default_probe_20260622.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "run_safe_goal_checks_20260620_ai_default_probe_20260622",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_digest_refresh_runs_before_remaining_operator_packet() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("final_evidence_fill_queue") < step_names.index(
        "final_input_autonomous_boundary_for_operator_packet"
    )
    assert step_names.index(
        "final_input_autonomous_boundary_for_operator_packet"
    ) < step_names.index("remaining_operator_evidence_digest")
    assert step_names.index("remaining_operator_evidence_digest") < step_names.index(
        "remaining_operator_input_packet"
    )
    assert step_names.index("remaining_operator_input_ready_validation") < step_names.index(
        "remaining_operator_final_review_pack"
    )
    assert step_names.index("remaining_operator_final_review_pack") < step_names.index(
        "minimum_operator_review_input"
    )
    assert step_names.index("minimum_operator_review_input") < step_names.index(
        "remaining_operator_decision_brief"
    )
    assert step_names.index("remaining_operator_decision_brief") < step_names.index(
        "remaining_operator_input_packet_sync"
    )
    assert step_names.index(
        "remaining_operator_input_ready_validation_after_sync"
    ) < step_names.index("remaining_operator_final_review_pack_after_sync")
    assert step_names.index(
        "remaining_operator_final_review_pack_after_sync"
    ) < step_names.index("minimum_operator_review_input_after_sync")
    assert step_names.index(
        "minimum_operator_review_input_after_sync"
    ) < step_names.index("remaining_operator_decision_brief_after_sync")
    assert step_names.index(
        "remaining_operator_decision_brief_after_sync"
    ) < step_names.index("remaining_operator_input_completion_simulation")
