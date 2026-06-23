import importlib.util
import sys
import unittest
from dataclasses import replace
from pathlib import Path


def _load_module() -> object:
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "tools" / "rakuraku_payment_confirm.py"
    spec = importlib.util.spec_from_file_location("rakuraku_payment_confirm", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[call-arg]
    return module


MODULE = _load_module()


class TestRakurakuPaymentConfirm(unittest.TestCase):
    def test_parse_result_summary_text(self) -> None:
        summary = MODULE._parse_result_summary_text(  # type: ignore[attr-defined]
            "表示件数 1000件 (659件中 1件～659件目)"
        )

        self.assertEqual(summary.total_count, 659)
        self.assertEqual(summary.range_start, 1)
        self.assertEqual(summary.range_end, 659)
        self.assertEqual(summary.display_count, 1000)

    def test_parse_selected_count_text(self) -> None:
        summary = MODULE._parse_selected_count_text(  # type: ignore[attr-defined]
            "659件中 2件が選択されています。"
        )

        self.assertEqual(summary.total_count, 659)
        self.assertEqual(summary.selected_count, 2)

    def test_parse_slip_row_text_extracts_bulk_transfer_method(self) -> None:
        text = (
            "00018300 2026/02/05 2026/02/06 2026/02/27 "
            "トヨタカローラ愛知株式会社 総合振込 1,234,567"
        )

        record = MODULE.parse_slip_row_text(text, "2026/02/27")  # type: ignore[attr-defined]

        self.assertEqual(record.slip_no, "00018300")
        self.assertEqual(record.payment_method, "総合振込")
        self.assertEqual(record.amount_yen, 1_234_567)

    def test_parse_slip_row_text_extracts_non_target_method(self) -> None:
        text = (
            "00016874 2025/12/05 2025/12/06 2025/12/30 "
            "株式会社庭昭 都度振込 44,000"
        )

        record = MODULE.parse_slip_row_text(text, "2025/12/30")  # type: ignore[attr-defined]

        self.assertEqual(record.payment_method, "都度振込")
        self.assertEqual(record.amount_yen, 44_000)

    def test_detect_payment_method_returns_none_for_unknown_method(self) -> None:
        method = MODULE._detect_payment_method(  # type: ignore[attr-defined]
            "00019999 2026/02/27 サンプル商事 123,456"
        )

        self.assertIsNone(method)

    def test_parse_slip_block_texts_extracts_grouped_rows(self) -> None:
        record = MODULE.parse_slip_block_texts(  # type: ignore[attr-defined]
            row1_text="00011452\n東海インプル建設株式会社\n瀬戸　阿紀子\n2025/01/05\n2025/01/06\n1,067\n2025/01/14\n保存不要",
            row2_text="東海建物管理株式会社",
            row3_text="TOCOビル 2F TIC専用(ガス料金) 12月分\n当方負担",
            checkbox_name="kakutei(11417)",
            page_no=1,
            row_group_index=1,
        )

        self.assertEqual(record.slip_no, "00011452")
        self.assertEqual(record.request_date, "2025/01/05")
        self.assertEqual(record.approval_date, "2025/01/06")
        self.assertEqual(record.payment_date, "2025/01/14")
        self.assertEqual(record.vendor, "東海建物管理株式会社")
        self.assertEqual(record.fee_burden, "当方負担")
        self.assertEqual(record.checkbox_name, "kakutei(11417)")

    def test_classify_slip_record_selects_matching_date_with_company_fee(self) -> None:
        record = MODULE.parse_slip_block_texts(  # type: ignore[attr-defined]
            row1_text="00011452\n東海インプル建設株式会社\n瀬戸　阿紀子\n2025/01/05\n2025/01/06\n1,067\n2025/01/14\n保存不要",
            row2_text="東海建物管理株式会社",
            row3_text="TOCOビル 2F TIC専用(ガス料金) 12月分\n当方負担",
            checkbox_name="kakutei(11417)",
            page_no=1,
            row_group_index=1,
        )
        record = replace(record, payment_method="総合振込", payment_method_source="detail_view")

        classified = MODULE.classify_slip_record(record, "2025/01/14")  # type: ignore[attr-defined]

        self.assertEqual(classified.decision, "selected")
        self.assertEqual(classified.decision_reason, "payment_date_match_and_company_fee")

    def test_classify_slip_record_marks_partner_fee_as_anomaly(self) -> None:
        record = MODULE.parse_slip_block_texts(  # type: ignore[attr-defined]
            row1_text="00011453\n東海インプル建設株式会社\n瀬戸　阿紀子\n2025/01/05\n2025/01/06\n1,392\n2025/01/14\n保存不要",
            row2_text="東海建物管理株式会社",
            row3_text="TOCOビル 3F-B(ガス料金) 12月分\n先方負担",
            checkbox_name="kakutei(11418)",
            page_no=1,
            row_group_index=2,
        )
        record = replace(record, payment_method="総合振込", payment_method_source="detail_view")

        classified = MODULE.classify_slip_record(record, "2025/01/14")  # type: ignore[attr-defined]

        self.assertEqual(classified.decision, "anomaly")
        self.assertEqual(classified.decision_reason, "non_company_fee_burden")

    def test_mark_company_fee_burden_allows_partner_fee_selection(self) -> None:
        record = MODULE.parse_slip_block_texts(  # type: ignore[attr-defined]
            row1_text="00011453\n東海インプル建設株式会社\n瀬戸　阿紀子\n2025/01/05\n2025/01/06\n1,392\n2025/01/14\n保存不要",
            row2_text="東海建物管理株式会社",
            row3_text="TOCOビル 3F-B(ガス料金) 12月分\n先方負担",
            checkbox_name="kakutei(11418)",
            page_no=1,
            row_group_index=2,
        )
        record = replace(record, payment_method="総合振込", payment_method_source="detail_view")

        updated = MODULE._mark_company_fee_burden(record, applied=True)  # type: ignore[attr-defined]
        classified = MODULE.classify_slip_record(updated, "2025/01/14")  # type: ignore[attr-defined]

        self.assertEqual(updated.fee_burden_before, "先方負担")
        self.assertEqual(updated.fee_burden, "当方負担")
        self.assertEqual(updated.fee_burden_action, "changed_to_company_fee")
        self.assertEqual(classified.decision, "selected")

    def test_classify_slip_record_marks_non_bulk_transfer_as_manual_excluded(self) -> None:
        record = MODULE.parse_slip_block_texts(  # type: ignore[attr-defined]
            row1_text="00016110\n東海インプル建設株式会社\n瀬戸　阿紀子\n2025/10/01\n2025/10/02\n1,000\n2025/10/31\n保存不要",
            row2_text="三菱ＨＣキャピタル株式会社",
            row3_text="リース料\n当方負担",
            checkbox_name="kakutei(16110)",
            page_no=1,
            row_group_index=1,
        )
        record = replace(record, payment_method="口座振替", payment_method_source="detail_view")

        classified = MODULE.classify_slip_record(record, "2025/10/31")  # type: ignore[attr-defined]

        self.assertEqual(classified.decision, "manual_excluded")
        self.assertEqual(classified.decision_reason, "manual_payment_method")

    def test_detect_detail_payment_method_reads_labeled_value(self) -> None:
        method = MODULE._detect_detail_payment_method(  # type: ignore[attr-defined]
            "支払方法\t口座振替\n右記の今回御請求高を口座振替致します。"
        )

        self.assertEqual(method, "口座振替")

    def test_validate_selection_expectations_accepts_matching_count_and_amount(self) -> None:
        record = MODULE.parse_slip_block_texts(  # type: ignore[attr-defined]
            row1_text="00011452\n東海インプル建設株式会社\n瀬戸　阿紀子\n2025/01/05\n2025/01/06\n1,067\n2025/01/14\n保存不要",
            row2_text="東海建物管理株式会社",
            row3_text="TOCOビル 2F TIC専用(ガス料金) 12月分\n当方負担",
            checkbox_name="kakutei(11417)",
            page_no=1,
            row_group_index=1,
        )

        total = MODULE.validate_selection_expectations(  # type: ignore[attr-defined]
            [record],
            expected_count=1,
            expected_total_amount_yen=1067,
        )

        self.assertEqual(total, 1067)

    def test_validate_selection_expectations_rejects_amount_mismatch(self) -> None:
        record = MODULE.parse_slip_block_texts(  # type: ignore[attr-defined]
            row1_text="00011452\n東海インプル建設株式会社\n瀬戸　阿紀子\n2025/01/05\n2025/01/06\n1,067\n2025/01/14\n保存不要",
            row2_text="東海建物管理株式会社",
            row3_text="TOCOビル 2F TIC専用(ガス料金) 12月分\n当方負担",
            checkbox_name="kakutei(11417)",
            page_no=1,
            row_group_index=1,
        )

        with self.assertRaisesRegex(RuntimeError, "合計金額"):
            MODULE.validate_selection_expectations(  # type: ignore[attr-defined]
                [record],
                expected_count=1,
                expected_total_amount_yen=999,
            )

    def test_validate_selection_expectations_can_defer_amount_when_fee_changes(self) -> None:
        record = MODULE.parse_slip_block_texts(  # type: ignore[attr-defined]
            row1_text="00011453\n東海インプル建設株式会社\n瀬戸　阿紀子\n2025/01/05\n2025/01/06\n1,392\n2025/01/14\n保存不要",
            row2_text="東海建物管理株式会社",
            row3_text="TOCOビル 3F-B(ガス料金) 12月分\n先方負担",
            checkbox_name="kakutei(11418)",
            page_no=1,
            row_group_index=2,
        )

        total = MODULE.validate_selection_expectations(  # type: ignore[attr-defined]
            [record],
            expected_count=1,
            expected_total_amount_yen=999,
            allow_amount_recalculation=True,
        )

        self.assertEqual(total, 1392)

    def test_local_mail_filter_removes_kanri_address(self) -> None:
        filtered = MODULE._filter_mail_addresses_for_env(  # type: ignore[attr-defined]
            ["kanri.tic@tokai-ic.co.jp", "kalimistk@gmail.com"],
            "LOCAL",
        )

        self.assertEqual(filtered, ["kalimistk@gmail.com"])

    def test_prod_mail_filter_keeps_kanri_address(self) -> None:
        filtered = MODULE._filter_mail_addresses_for_env(  # type: ignore[attr-defined]
            ["kanri.tic@tokai-ic.co.jp"],
            "PROD",
        )

        self.assertEqual(filtered, ["kanri.tic@tokai-ic.co.jp"])

    def test_apply_mail_config_allows_blank_cc_in_local(self) -> None:
        original = (
            list(MODULE.MAIL_TO_SUCCESS),
            list(MODULE.MAIL_TO_ERROR),
            list(MODULE.MAIL_CC_ERROR),
        )
        try:
            MODULE.MAIL_TO_SUCCESS = ["kanri.tic@tokai-ic.co.jp"]
            MODULE.MAIL_TO_ERROR = ["kanri.tic@tokai-ic.co.jp"]
            MODULE.MAIL_CC_ERROR = ["kalimistk@gmail.com"]

            MODULE._apply_mail_config(  # type: ignore[attr-defined]
                {
                    "MAIL_TO_SUCCESS": "kalimistk@gmail.com",
                    "MAIL_TO_ERROR": "kalimistk@gmail.com",
                    "MAIL_CC_ERROR": "",
                },
                "LOCAL",
            )

            self.assertEqual(MODULE.MAIL_TO_SUCCESS, ["kalimistk@gmail.com"])
            self.assertEqual(MODULE.MAIL_TO_ERROR, ["kalimistk@gmail.com"])
            self.assertEqual(MODULE.MAIL_CC_ERROR, [])
        finally:
            MODULE.MAIL_TO_SUCCESS, MODULE.MAIL_TO_ERROR, MODULE.MAIL_CC_ERROR = original
