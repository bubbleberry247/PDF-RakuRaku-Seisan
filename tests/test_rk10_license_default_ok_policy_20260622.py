from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RISKY_RADIO_INVOKES = (
    'control_automation_id(control) == "DevelopmentLicenseCheckBox":',
    'control_automation_id(control) == "DevelopmentWithAiLicenseCheckBox":',
)


def test_rks_editor_probes_leave_ai_development_default_and_press_ok_only() -> None:
    probe_paths = [
        ROOT / "tools" / "run_rks_editor_open_build_probe_20260620.py",
        ROOT
        / "tools"
        / "run_rks_editor_open_build_probe_20260620_safe_exe_default_20260622.py",
    ]

    for probe_path in probe_paths:
        source = probe_path.read_text(encoding="utf-8")

        for risky_invoke in RISKY_RADIO_INVOKES:
            assert risky_invoke not in source
        assert 'control_text(control) == "OK"' in source
