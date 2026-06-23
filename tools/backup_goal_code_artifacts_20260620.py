"""Back up RK10 goal helper code artifacts under a separate report folder.

This tool copies the local checker/test files referenced by the fixed safe
runner into a timestamped repository report directory and records size/SHA256.
It does not read production data or operate external systems.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
RUNNER_PATH = ROOT / "tools" / "run_safe_goal_checks_20260620.py"
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_code_artifact_backups_20260620"


@dataclass(frozen=True)
class BackupArtifact:
    source_path: str
    backup_path: str
    role: str
    source_exists: bool
    size_bytes: int
    sha256: str


def load_runner_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("run_safe_goal_checks_20260620_for_backup", path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"could not load runner module: {path}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def role_from_constant(name: str) -> str:
    if name.startswith("CHECK_"):
        return "tool"
    if name.startswith("TEST_"):
        return "test"
    return "other"


def collect_runner_artifacts(runner_path: Path | None = None) -> list[tuple[str, Path]]:
    module = load_runner_module(runner_path or RUNNER_PATH)
    rows = []
    for name, value in vars(module).items():
        if not name.startswith(("CHECK_", "TEST_")):
            continue
        if not isinstance(value, Path):
            continue
        if value.suffix.lower() != ".py":
            continue
        rows.append((name, value))
    return sorted(rows, key=lambda row: str(row[1]).lower())


def backup_path_for(source_path: Path, snapshot_dir: Path) -> Path:
    relative_path = source_path.relative_to(ROOT)
    return snapshot_dir / "files" / relative_path


def build_artifact(name: str, source_path: Path, snapshot_dir: Path) -> BackupArtifact:
    backup_path = backup_path_for(source_path, snapshot_dir)
    if not source_path.exists():
        return BackupArtifact(
            source_path=str(source_path),
            backup_path=str(backup_path),
            role=role_from_constant(name),
            source_exists=False,
            size_bytes=0,
            sha256="",
        )
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, backup_path)
    return BackupArtifact(
        source_path=str(source_path),
        backup_path=str(backup_path),
        role=role_from_constant(name),
        source_exists=True,
        size_bytes=source_path.stat().st_size,
        sha256=file_sha256(source_path),
    )


def build_payload(out_dir: Path, snapshot_id: str) -> dict[str, Any]:
    snapshot_dir = out_dir / snapshot_id
    artifacts = [
        build_artifact(name, source_path, snapshot_dir)
        for name, source_path in collect_runner_artifacts()
    ]
    missing_count = sum(1 for artifact in artifacts if not artifact.source_exists)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "backup_complete": missing_count == 0 and bool(artifacts),
        "safety": "local code artifact backup only; no production data read or external operation",
        "runner_path": str(RUNNER_PATH),
        "out_dir": str(out_dir),
        "snapshot_id": snapshot_id,
        "snapshot_dir": str(snapshot_dir),
        "artifact_count": len(artifacts),
        "missing_count": missing_count,
        "tool_count": sum(1 for artifact in artifacts if artifact.role == "tool"),
        "test_count": sum(1 for artifact in artifacts if artifact.role == "test"),
        "artifacts": [asdict(artifact) for artifact in artifacts],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, list)
    lines = [
        "# 目標コード別名保存 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- backup_complete: `{payload['backup_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- snapshot_dir: `{payload['snapshot_dir']}`",
        f"- artifact_count: `{payload['artifact_count']}`",
        f"- missing_count: `{payload['missing_count']}`",
        f"- tool_count: `{payload['tool_count']}`",
        f"- test_count: `{payload['test_count']}`",
        "",
        "## Boundary",
        "",
        "- This backs up helper code and tests used by the safe fixed runner.",
        "- It does not back up production data, customer files, Outlook content, RK10 runtime state, or payment evidence.",
        "",
        "## Artifact Matrix",
        "",
        "| Role | Source Exists | Size | SHA256 | Source | Backup |",
        "|---|---:|---:|---|---|---|",
    ]
    for artifact in artifacts:
        assert isinstance(artifact, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(artifact["role"]),
                    "YES" if artifact["source_exists"] else "NO",
                    str(artifact["size_bytes"]),
                    f"`{artifact['sha256']}`" if artifact["sha256"] else "-",
                    f"`{artifact['source_path']}`",
                    f"`{artifact['backup_path']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "goal_code_artifact_backups.json"
    md_path = out_dir / "goal_code_artifact_backups.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def default_snapshot_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Back up goal helper code artifacts.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--snapshot-id", default=default_snapshot_id())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.out_dir, args.snapshot_id)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["backup_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
