import csv
import tempfile
import unittest
from pathlib import Path

from src.audit_score_reference import SHARED_FIELDS, audit_score_reference


class ScoreReferenceTests(unittest.TestCase):
    def test_distinguishes_recorded_scores_from_fills_and_checks_row_order(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw.csv"
            cleaned = Path(directory) / "cleaned.csv"
            games = [
                {"title": "Recorded", "total_sales": "0", "critic_score": "7.3"},
                {"title": "Missing", "total_sales": "1.0", "critic_score": ""},
            ]
            with raw.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=[*SHARED_FIELDS, "critic_score", "release_date"])
                writer.writeheader()
                writer.writerows(game | {"release_date": "31-12-2018"} for game in games)

            def write_reference(rows):
                with cleaned.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=[*SHARED_FIELDS, "critic_score", "release_year"])
                    writer.writeheader()
                    writer.writerows(
                        game | {"critic_score": "7.3", "developer": "Unknown", "release_year": "2018.0"}
                        for game in rows
                    )

            write_reference(games)
            summary = audit_score_reference(raw, cleaned)
            self.assertEqual(summary["raw_observed_7_3"], 1)
            self.assertEqual(summary["fill_value_counts"], {"7.3": 1})
            self.assertEqual(summary["observed_scores_changed"], 0)

            write_reference(reversed(games))
            with self.assertRaisesRegex(ValueError, "shared field 'title' differs"):
                audit_score_reference(raw, cleaned)
