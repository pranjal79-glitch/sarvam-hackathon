import unittest

import pandas as pd

from backend import analyze_transactions, categorize, prepare_transactions, sample_data


class PrepareTransactionsTests(unittest.TestCase):
    def test_normalizes_headers_and_skips_invalid_rows(self):
        source = pd.DataFrame(
            {
                " Date ": ["2026-10-01", "not-a-date", "2026-10-03"],
                " DESCRIPTION ": ["  Client payment ", "Rent", ""],
                " Amount ": ["₹1,200", "-500", "100"],
            }
        )

        result, rejected = prepare_transactions(source)

        self.assertEqual(rejected, 2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["description"], "Client payment")
        self.assertEqual(result.iloc[0]["amount"], 1200)
        self.assertEqual(result.iloc[0]["type"], "Income")

    def test_rejects_missing_required_columns(self):
        with self.assertRaisesRegex(ValueError, "missing required"):
            prepare_transactions(pd.DataFrame({"date": ["2026-10-01"]}))

    def test_rejects_duplicate_normalized_columns(self):
        source = pd.DataFrame(
            [["2026-10-01", "Rent", -500, "Other"]],
            columns=["date", "description", "amount", " DATE "],
        )
        with self.assertRaisesRegex(ValueError, "duplicate column"):
            prepare_transactions(source)

    def test_rejects_files_with_no_valid_rows(self):
        source = pd.DataFrame(
            {"date": ["invalid"], "description": ["Rent"], "amount": ["bad"]}
        )
        with self.assertRaisesRegex(ValueError, "No valid transactions"):
            prepare_transactions(source)


class AnalysisTests(unittest.TestCase):
    def test_summary_separates_income_expenses_and_neutral_transactions(self):
        source = pd.DataFrame(
            {
                "date": ["2026-10-01", "2026-10-02", "2026-10-03"],
                "description": ["Client payment", "Office rent", "Adjustment"],
                "amount": [1200, -500, 0],
            }
        )
        transactions, _ = prepare_transactions(source)

        summary = analyze_transactions(transactions)

        self.assertEqual(summary["income"], 1200)
        self.assertEqual(summary["expenses"], 500)
        self.assertEqual(summary["net_cashflow"], 700)
        self.assertEqual(summary["transaction_count"], 3)
        self.assertIn("Neutral", set(summary["monthly"]["type"]))
        self.assertEqual(summary["expense_categories"].iloc[0]["category"], "Housing")

    def test_sample_data_has_expected_totals(self):
        transactions, rejected = prepare_transactions(sample_data())
        summary = analyze_transactions(transactions)

        self.assertEqual(rejected, 0)
        self.assertEqual(summary["transaction_count"], 18)
        self.assertEqual(summary["income"], 285000)
        self.assertEqual(summary["expenses"], 76900)
        self.assertEqual(summary["net_cashflow"], 208100)

    def test_categorizes_common_expense_types(self):
        self.assertEqual(categorize("Monthly electricity bill"), "Utilities")
        self.assertEqual(categorize("Hospital visit"), "Healthcare")
        self.assertEqual(categorize("Unrecognized transaction"), "Other")


if __name__ == "__main__":
    unittest.main()
