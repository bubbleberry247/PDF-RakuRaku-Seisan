"""Validate operator evidence fields in RK10 goal execution packet CSVs.

This checker only reads bundle CSVs and evidence paths, then writes repository
reports. It does not open Outlook, RK10, Rakuraku, Azure, printers, mail,
payment systems, MainSV, or production files.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_PACKET_DIR = ROOT / "plans" / "reports" / "goal_execution_packet_20260620"
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_execution_packet_validation_20260620"
DEFAULT_BUNDLE_SHEET = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_operator_sheet_20260620"
    / "bundle_operator_sheet.csv"
)
OPERATOR_FIELDS = ["operator_result", "evidence_path", "reviewer", "reviewed_at"]
ATTENTION_FIELDS = [
    "level",
    "bundle",
    "scenario",
    "status",
    "missing_fields",
    "target_csv",
    "bundle_sheet_path",
    "evidence_path",
    "cleanup_evidence_path",
    "next_action",
]
APPROVED_RESULTS = {
    "approved",
    "complete",
    "completed",
    "ok",
    "pass",
    "passed",
    "実施済",
    "完了",
    "承認",
    "承認済",
    "済",
}
YES_VALUES = {"1", "true", "yes", "y", "used", "created", "はい", "あり", "有", "作成", "作成済"}
CLEANUP_DONE_RESULTS = {
    "deleted",
    "delete_done",
    "removed",
    "cleanup_complete",
    "ok",
    "done",
    "削除",
    "削除済",
    "削除完了",
    "完了",
    "済",
}


@dataclass(frozen=True)
class PacketRowValidation:
    csv_path: str
    scenario: str
    bundle: str
    operator_result: str
    evidence_path: str
    reviewer: str
    reviewed_at: str
    rakuraku_customer_login_used: str
    temporary_save_created: str
    created_data_cleanup_status: str
    created_data_cleanup_evidence_path: str
    cleanup_reviewer: str
    cleanup_reviewed_at: str
    status: str
    missing_fields: str
    evidence_exists: bool
    cleanup_evidence_exists: bool

    @property
    def approved(self) -> bool:
        return self.status in {
            "APPROVED_WITH_EVIDENCE",
            "APPROVED_BY_BUNDLE_WITH_EVIDENCE",
        }


@dataclass(frozen=True)
class BundleApproval:
    bundle: str
    operator_result: str
    evidence_path: str
    reviewer: str
    reviewed_at: str
    rakuraku_customer_login_used: str
    temporary_save_created: str
    created_data_cleanup_status: str
    created_data_cleanup_evidence_path: str
    cleanup_reviewer: str
    cleanup_reviewed_at: str
    status: str
    missing_fields: str
    evidence_exists: bool
    cleanup_evidence_exists: bool

    @property
    def approved(self) -> bool:
        return self.status == "APPROVED_WITH_EVIDENCE"


@dataclass(frozen=True)
class AttentionRow:
    level: str
    bundle: str
    scenario: str
    status: str
    missing_fields: str
    target_csv: str
    bundle_sheet_path: str
    evidence_path: str
    cleanup_evidence_path: str
    next_action: str


def normalize_result(value: str) -> str:
    return value.strip().lower()


def is_yes(value: str) -> bool:
    return normalize_result(value) in YES_VALUES


def evidence_path_exists(value: str) -> bool:
    if not value.strip():
        return False
    return Path(value.strip()).exists()


def validate_cleanup_fields(
    rakuraku_customer_login_used: str,
    temporary_save_created: str,
    created_data_cleanup_status: str,
    created_data_cleanup_evidence_path: str,
    cleanup_reviewer: str,
    cleanup_reviewed_at: str,
) -> tuple[str, str, bool]:
    cleanup_evidence_exists = evidence_path_exists(created_data_cleanup_evidence_path)
    return "", "", cleanup_evidence_exists


def validate_operator_fields(
    operator_result: str,
    evidence_path: str,
    reviewer: str,
    reviewed_at: str,
) -> tuple[str, str, bool]:
    missing_fields = [
        field
        for field, value in [
            ("operator_result", operator_result),
            ("evidence_path", evidence_path),
            ("reviewer", reviewer),
            ("reviewed_at", reviewed_at),
        ]
        if not value
    ]
    evidence_exists = evidence_path_exists(evidence_path)
    if missing_fields:
        return "MISSING_OPERATOR_FIELDS", ", ".join(missing_fields), evidence_exists
    if normalize_result(operator_result) not in APPROVED_RESULTS:
        return "OPERATOR_RESULT_NOT_APPROVED", "", evidence_exists
    if not evidence_exists:
        return "EVIDENCE_FILE_NOT_FOUND", "", evidence_exists
    return "APPROVED_WITH_EVIDENCE", "", evidence_exists


def apply_cleanup_gate(
    status: str,
    missing_fields: str,
    rakuraku_customer_login_used: str,
    temporary_save_created: str,
    created_data_cleanup_status: str,
    created_data_cleanup_evidence_path: str,
    cleanup_reviewer: str,
    cleanup_reviewed_at: str,
) -> tuple[str, str, bool]:
    cleanup_status, cleanup_missing_fields, cleanup_evidence_exists = validate_cleanup_fields(
        rakuraku_customer_login_used,
        temporary_save_created,
        created_data_cleanup_status,
        created_data_cleanup_evidence_path,
        cleanup_reviewer,
        cleanup_reviewed_at,
    )
    if not cleanup_status:
        return status, missing_fields, cleanup_evidence_exists
    if status in {"APPROVED_WITH_EVIDENCE", "APPROVED_BY_BUNDLE_WITH_EVIDENCE"}:
        return cleanup_status, cleanup_missing_fields, cleanup_evidence_exists
    combined_missing = ", ".join(
        part for part in [missing_fields, cleanup_missing_fields] if part
    )
    return status, combined_missing, cleanup_evidence_exists


def read_bundle_approvals(bundle_sheet_path: Path) -> dict[str, BundleApproval]:
    if not bundle_sheet_path.exists():
        return {}
    approvals: dict[str, BundleApproval] = {}
    with bundle_sheet_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            bundle = str(row.get("bundle", "")).strip()
            if not bundle:
                continue
            operator_result = str(row.get("operator_result", "")).strip()
            evidence_path = str(row.get("evidence_path", "")).strip()
            reviewer = str(row.get("reviewer", "")).strip()
            reviewed_at = str(row.get("reviewed_at", "")).strip()
            rakuraku_customer_login_used = str(row.get("rakuraku_customer_login_used", "")).strip()
            temporary_save_created = str(row.get("temporary_save_created", "")).strip()
            created_data_cleanup_status = str(row.get("created_data_cleanup_status", "")).strip()
            created_data_cleanup_evidence_path = str(
                row.get("created_data_cleanup_evidence_path", "")
            ).strip()
            cleanup_reviewer = str(row.get("cleanup_reviewer", "")).strip()
            cleanup_reviewed_at = str(row.get("cleanup_reviewed_at", "")).strip()
            status, missing_fields, evidence_exists = validate_operator_fields(
                operator_result,
                evidence_path,
                reviewer,
                reviewed_at,
            )
            status, missing_fields, cleanup_evidence_exists = apply_cleanup_gate(
                status,
                missing_fields,
                rakuraku_customer_login_used,
                temporary_save_created,
                created_data_cleanup_status,
                created_data_cleanup_evidence_path,
                cleanup_reviewer,
                cleanup_reviewed_at,
            )
            approvals[bundle] = BundleApproval(
                bundle=bundle,
                operator_result=operator_result,
                evidence_path=evidence_path,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
                rakuraku_customer_login_used=rakuraku_customer_login_used,
                temporary_save_created=temporary_save_created,
                created_data_cleanup_status=created_data_cleanup_status,
                created_data_cleanup_evidence_path=created_data_cleanup_evidence_path,
                cleanup_reviewer=cleanup_reviewer,
                cleanup_reviewed_at=cleanup_reviewed_at,
                status=status,
                missing_fields=missing_fields,
                evidence_exists=evidence_exists,
                cleanup_evidence_exists=cleanup_evidence_exists,
            )
    return approvals


def validate_row(
    row: dict[str, str],
    csv_path: Path,
    bundle_approvals: dict[str, BundleApproval] | None = None,
) -> PacketRowValidation:
    operator_result = str(row.get("operator_result", "")).strip()
    evidence_path = str(row.get("evidence_path", "")).strip()
    reviewer = str(row.get("reviewer", "")).strip()
    reviewed_at = str(row.get("reviewed_at", "")).strip()
    rakuraku_customer_login_used = str(row.get("rakuraku_customer_login_used", "")).strip()
    temporary_save_created = str(row.get("temporary_save_created", "")).strip()
    created_data_cleanup_status = str(row.get("created_data_cleanup_status", "")).strip()
    created_data_cleanup_evidence_path = str(
        row.get("created_data_cleanup_evidence_path", "")
    ).strip()
    cleanup_reviewer = str(row.get("cleanup_reviewer", "")).strip()
    cleanup_reviewed_at = str(row.get("cleanup_reviewed_at", "")).strip()
    status, missing_fields, evidence_exists = validate_operator_fields(
        operator_result,
        evidence_path,
        reviewer,
        reviewed_at,
    )
    bundle = str(row.get("bundle", "")).strip()
    bundle_approval = (bundle_approvals or {}).get(bundle)
    if status == "MISSING_OPERATOR_FIELDS" and bundle_approval and bundle_approval.approved:
        operator_result = bundle_approval.operator_result
        evidence_path = bundle_approval.evidence_path
        reviewer = bundle_approval.reviewer
        reviewed_at = bundle_approval.reviewed_at
        rakuraku_customer_login_used = bundle_approval.rakuraku_customer_login_used
        temporary_save_created = bundle_approval.temporary_save_created
        created_data_cleanup_status = bundle_approval.created_data_cleanup_status
        created_data_cleanup_evidence_path = bundle_approval.created_data_cleanup_evidence_path
        cleanup_reviewer = bundle_approval.cleanup_reviewer
        cleanup_reviewed_at = bundle_approval.cleanup_reviewed_at
        status = "APPROVED_BY_BUNDLE_WITH_EVIDENCE"
        missing_fields = ""
        evidence_exists = True
    status, missing_fields, cleanup_evidence_exists = apply_cleanup_gate(
        status,
        missing_fields,
        rakuraku_customer_login_used,
        temporary_save_created,
        created_data_cleanup_status,
        created_data_cleanup_evidence_path,
        cleanup_reviewer,
        cleanup_reviewed_at,
    )
    return PacketRowValidation(
        csv_path=str(csv_path),
        scenario=str(row.get("scenario", "")).strip(),
        bundle=bundle,
        operator_result=operator_result,
        evidence_path=evidence_path,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        rakuraku_customer_login_used=rakuraku_customer_login_used,
        temporary_save_created=temporary_save_created,
        created_data_cleanup_status=created_data_cleanup_status,
        created_data_cleanup_evidence_path=created_data_cleanup_evidence_path,
        cleanup_reviewer=cleanup_reviewer,
        cleanup_reviewed_at=cleanup_reviewed_at,
        status=status,
        missing_fields=missing_fields,
        evidence_exists=evidence_exists,
        cleanup_evidence_exists=cleanup_evidence_exists,
    )


def find_packet_csvs(packet_dir: Path) -> list[Path]:
    if not packet_dir.exists():
        return []
    return sorted(packet_dir.glob("*_bundle.csv"))


def validate_packet_csv(
    csv_path: Path,
    bundle_approvals: dict[str, BundleApproval] | None = None,
) -> list[PacketRowValidation]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            validate_row(row, csv_path, bundle_approvals)
            for row in csv.DictReader(handle)
        ]


def build_payload(
    packet_dir: Path,
    bundle_sheet_path: Path = DEFAULT_BUNDLE_SHEET,
) -> dict[str, Any]:
    csv_paths = find_packet_csvs(packet_dir)
    bundle_approvals = read_bundle_approvals(bundle_sheet_path)
    rows = [
        row
        for csv_path in csv_paths
        for row in validate_packet_csv(csv_path, bundle_approvals)
    ]
    approved_count = sum(1 for row in rows if row.approved)
    needs_attention_count = len(rows) - approved_count
    approved_bundle_count = sum(
        1 for approval in bundle_approvals.values() if approval.approved
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "all_packet_rows_approved": bool(rows) and needs_attention_count == 0,
        "safety": "read-only CSV/evidence-path validation; repository report writes only",
        "packet_dir": str(packet_dir),
        "bundle_sheet_path": str(bundle_sheet_path),
        "bundle_sheet_exists": bundle_sheet_path.exists(),
        "bundle_approval_count": len(bundle_approvals),
        "approved_bundle_count": approved_bundle_count,
        "packet_csv_count": len(csv_paths),
        "row_count": len(rows),
        "approved_row_count": approved_count,
        "needs_attention_count": needs_attention_count,
        "attention_row_count": 0,
        "attention_csv_path": "",
        "missing_packet_dir": not packet_dir.exists(),
        "bundle_approvals": [
            asdict(approval) | {"approved": approval.approved}
            for approval in bundle_approvals.values()
        ],
        "rows": [asdict(row) | {"approved": row.approved} for row in rows],
    }


def next_attention_action(status: str) -> str:
    if status == "MISSING_OPERATOR_FIELDS":
        return "operator_result/evidence_path/reviewer/reviewed_atを記入し、evidence_pathを実在パスにする"
    if status == "OPERATOR_RESULT_NOT_APPROVED":
        return "operator_resultをOK/PASS/完了/承認済などの承認済み値にする"
    if status == "EVIDENCE_FILE_NOT_FOUND":
        return "evidence_pathを実在する証跡ファイルまたはフォルダへ修正する"
    return "検証レポートのstatusとmissing_fieldsに従って入力を修正する"


def build_attention_rows(payload: dict[str, Any]) -> list[AttentionRow]:
    bundle_sheet_path = str(payload.get("bundle_sheet_path", ""))
    attention_rows: list[AttentionRow] = []
    for approval in payload.get("bundle_approvals", []):
        if not isinstance(approval, dict) or bool(approval.get("approved")):
            continue
        status = str(approval.get("status", ""))
        attention_rows.append(
            AttentionRow(
                level="bundle",
                bundle=str(approval.get("bundle", "")),
                scenario="*",
                status=status,
                missing_fields=str(approval.get("missing_fields", "")),
                target_csv=bundle_sheet_path,
                bundle_sheet_path=bundle_sheet_path,
                evidence_path=str(approval.get("evidence_path", "")),
                cleanup_evidence_path=str(approval.get("created_data_cleanup_evidence_path", "")),
                next_action=next_attention_action(status),
            )
        )
    for row in payload.get("rows", []):
        if not isinstance(row, dict) or bool(row.get("approved")):
            continue
        status = str(row.get("status", ""))
        attention_rows.append(
            AttentionRow(
                level="scenario",
                bundle=str(row.get("bundle", "")),
                scenario=str(row.get("scenario", "")),
                status=status,
                missing_fields=str(row.get("missing_fields", "")),
                target_csv=str(row.get("csv_path", "")),
                bundle_sheet_path=bundle_sheet_path,
                evidence_path=str(row.get("evidence_path", "")),
                cleanup_evidence_path=str(row.get("created_data_cleanup_evidence_path", "")),
                next_action=next_attention_action(status),
            )
        )
    return attention_rows


def write_attention_csv(path: Path, attention_rows: list[AttentionRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ATTENTION_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in attention_rows)


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# 目標実行パケット証跡検証 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- all_packet_rows_approved: `{payload['all_packet_rows_approved']}`",
        f"- safety: `{payload['safety']}`",
        f"- packet_dir: `{payload['packet_dir']}`",
        f"- bundle_sheet_path: `{payload['bundle_sheet_path']}`",
        f"- bundle_sheet_exists: `{payload['bundle_sheet_exists']}`",
        f"- bundle_approval_count: `{payload['bundle_approval_count']}`",
        f"- approved_bundle_count: `{payload['approved_bundle_count']}`",
        f"- packet_csv_count: `{payload['packet_csv_count']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- approved_row_count: `{payload['approved_row_count']}`",
        f"- needs_attention_count: `{payload['needs_attention_count']}`",
        f"- attention_row_count: `{payload.get('attention_row_count', 0)}`",
        f"- attention_csv_path: `{payload.get('attention_csv_path', '')}`",
        f"- missing_packet_dir: `{payload['missing_packet_dir']}`",
        "",
        "## 判定ルール",
        "",
        "- `operator_result` は `OK` / `PASS` / `APPROVED` / `完了` / `承認済` などの承認済み値のみ通過。",
        "- `evidence_path` は空欄不可で、ファイルまたはフォルダが実在している必要がある。",
        "- `reviewer` と `reviewed_at` は空欄不可。",
        "- 個別CSV行が空欄でも、6束オペレーター入力シートの同Bundle行が承認済みなら `APPROVED_BY_BUNDLE_WITH_EVIDENCE` として通過。",
        "- `rakuraku_customer_login_used` / `temporary_save_created` / cleanup系列は任意記録欄。削除証跡は承認ゲートの必須条件にしない。",
        "- この検証は証跡の存在確認だけで、実メール・実印刷・支払実行・本番申請は行わない。",
        "",
        "## Bundle Approval Matrix",
        "",
        "| Bundle | Status | Missing Fields | Evidence Exists | Cleanup Evidence Exists | Evidence Path | Cleanup Evidence Path |",
        "|---|---|---|---:|---:|---|---|",
    ]
    bundle_approvals = payload["bundle_approvals"]
    assert isinstance(bundle_approvals, list)
    for approval in bundle_approvals:
        assert isinstance(approval, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(approval["bundle"]),
                    str(approval["status"]),
                    str(approval["missing_fields"]) or "-",
                    "YES" if approval["evidence_exists"] else "NO",
                    "YES" if approval["cleanup_evidence_exists"] else "NO",
                    f"`{approval['evidence_path']}`" if approval["evidence_path"] else "-",
                    (
                        f"`{approval['created_data_cleanup_evidence_path']}`"
                        if approval["created_data_cleanup_evidence_path"]
                        else "-"
                    ),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Row Matrix",
            "",
            "| Bundle | Scenario | Status | Missing Fields | Evidence Exists | Cleanup Evidence Exists | Evidence Path | Cleanup Evidence Path | CSV |",
            "|---|---|---|---|---:|---:|---|---|---|",
        ]
    )
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["bundle"]),
                    str(row["scenario"]),
                    str(row["status"]),
                    str(row["missing_fields"]) or "-",
                    "YES" if row["evidence_exists"] else "NO",
                    "YES" if row["cleanup_evidence_exists"] else "NO",
                    f"`{row['evidence_path']}`" if row["evidence_path"] else "-",
                    (
                        f"`{row['created_data_cleanup_evidence_path']}`"
                        if row["created_data_cleanup_evidence_path"]
                        else "-"
                    ),
                    f"`{row['csv_path']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate RK10 goal execution packet evidence.")
    parser.add_argument("--packet-dir", type=Path, default=DEFAULT_PACKET_DIR)
    parser.add_argument("--bundle-sheet", type=Path, default=DEFAULT_BUNDLE_SHEET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.packet_dir, args.bundle_sheet)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "goal_execution_packet_validation.json"
    md_path = args.out_dir / "goal_execution_packet_validation.md"
    attention_csv_path = args.out_dir / "goal_execution_packet_attention.csv"
    attention_rows = build_attention_rows(payload)
    payload["attention_row_count"] = len(attention_rows)
    payload["attention_csv_path"] = str(attention_csv_path)
    write_attention_csv(attention_csv_path, attention_rows)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
