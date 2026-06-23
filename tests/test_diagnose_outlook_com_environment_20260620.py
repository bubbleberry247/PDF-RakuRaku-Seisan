import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "diagnose_outlook_com_environment_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("diagnose_outlook_com_environment_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_executable_path_handles_quoted_command() -> None:
    module = load_module()

    result = module.extract_executable_path(
        r'"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE" /embedding'
    )

    assert result == r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE"


def test_classify_environment_requires_classic_outlook_when_not_running() -> None:
    module = load_module()
    rows = [
        module.CheckRow("path:s12_tool", "OK", "", ""),
        module.CheckRow("python_module:win32com.client", "OK", "", ""),
        module.CheckRow("registry:Outlook.Application\\CLSID", "OK", "", ""),
        module.CheckRow("process:OUTLOOK.EXE", "NOT_RUNNING", "", ""),
    ]
    last_result = {
        "status": "OUTLOOK_COM_NOT_ATTACHABLE_OR_STARTABLE",
        "hresult_codes": ["-2146959355", "-2147221021"],
    }

    status, diagnosis, next_action = module.classify_environment(rows, last_result)

    assert status == "CLASSIC_OUTLOOK_DESKTOP_SESSION_REQUIRED"
    assert "Outlook COM is registered" in diagnosis
    assert "Open Classic Outlook" in next_action


def test_classify_environment_blocks_missing_pywin32() -> None:
    module = load_module()
    rows = [
        module.CheckRow("path:s12_tool", "OK", "", ""),
        module.CheckRow("python_module:win32com.client", "MISSING", "", ""),
    ]

    status, _diagnosis, next_action = module.classify_environment(rows, {})

    assert status == "PYWIN32_MISSING"
    assert "pywin32" in next_action


def test_classify_environment_identifies_running_outlook_rejection() -> None:
    module = load_module()
    rows = [
        module.CheckRow("path:s12_tool", "OK", "", ""),
        module.CheckRow("python_module:win32com.client", "OK", "", ""),
        module.CheckRow("registry:Outlook.Application\\CLSID", "OK", "", ""),
        module.CheckRow("process:OUTLOOK.EXE", "RUNNING", "", ""),
    ]
    last_result = {
        "status": "OUTLOOK_COM_NOT_ATTACHABLE_OR_STARTABLE",
        "hresult_codes": ["-2146959355", "-2147221021"],
    }

    status, diagnosis, next_action = module.classify_environment(rows, last_result)

    assert status == "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED"
    assert "COM is registered" in diagnosis
    assert "Close all Outlook windows" in next_action


def test_summarize_process_detail_reports_pid_session_and_path() -> None:
    module = load_module()

    detail = module.summarize_process_detail(
        '{"ProcessId":42916,"SessionId":1,'
        '"ExecutablePath":"C:\\\\Program Files\\\\Microsoft Office\\\\Root\\\\Office16\\\\OUTLOOK.EXE"}'
    )

    assert "pid=42916" in detail
    assert "session=1" in detail
    assert "OUTLOOK.EXE" in detail
