import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.prepare_data import DATASET_VERSION, RAW_COLUMNS, prepare_dataset


def game(**overrides):
    row = {
        "title": "A game",
        "console": "PS3",
        "publisher": "NA",
        "critic_score": "7.3",
        "total_sales": "1.01",
        "na_sales": "0.25",
        "jp_sales": "0",
        "pal_sales": "0.50",
        "other_sales": "0.25",
        "release_date": "31-12-2018",
    }
    return row | overrides


class PrepareDatasetTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.raw_path = self.root / "raw.csv"
        self.output = self.root / "processed"

    def write_raw(self, rows):
        with self.raw_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=RAW_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return hashlib.sha256(self.raw_path.read_bytes()).hexdigest()

    def prepare(self, rows):
        checksum = self.write_raw(rows)
        with patch("src.prepare_data.RAW_SHA256", checksum):
            return prepare_dataset(self.raw_path, self.output)

    def read_output(self, name):
        return pd.read_csv(self.output / name, keep_default_na=False)

    def test_curates_rows_without_filling_scores_or_regional_sales(self):
        row = game()
        self.prepare([
            row,
            row,
            game(title="  A GAME ", console="PS4", critic_score="", jp_sales=""),
            game(title="Zero", total_sales="0", jp_sales="0"),
            game(title="Mismatch", total_sales="1.03"),
            game(title="Bad label", total_sales="-1"),
            game(title="Bad date", release_date="31-02-2018"),
            game(title="Outside", release_date="01-01-2019"),
            game(title="Conflict", developer="One"),
            game(title=" conflict ", developer="Two"),
            game(title="Regional zeros", total_sales="0.01", na_sales="0", pal_sales="0", other_sales="0"),
        ])
        audited = self.read_output("games_audited.csv")
        main = self.read_output("games_main.csv")
        self.assertEqual(audited["source_row"].tolist(), list(range(1, 12)))
        self.assertEqual(main["source_row"].tolist(), [1, 3, 4, 5, 9, 10, 11])
        self.assertEqual(main["title_group"].tolist()[:4], ["a game", "a game", "zero", "mismatch"])
        self.assertEqual(main["critic_score"].tolist()[:4], ["7.3", "", "7.3", "7.3"])
        self.assertEqual(main["jp_sales"].tolist()[:4], ["0.0", "", "0.0", "0.0"])
        self.assertEqual(main["publisher"].tolist(), ["NA"] * 7)
        self.assertEqual(main["regional_status"].tolist()[:4], [
            "comparable", "missing_or_invalid_sales", "nonpositive_total", "regional_total_mismatch",
        ])
        self.assertEqual(main["regional_status"].iloc[-1], "nonpositive_regional_sum")
        self.assertEqual(main["title_console_conflict"].tolist(), [False] * 4 + [True, True, False])
        self.assertEqual(audited["main_exclusion"].tolist(), [
            "included", "exact_duplicate", "included", "included", "included",
            "missing_or_invalid_total_sales", "missing_or_invalid_release_date",
            "outside_main_window", "included", "included", "included",
        ])

    def test_rebuild_is_identical_and_protects_existing_outputs(self):
        checksum = self.write_raw([game()])
        second_output = self.root / "another-output"
        with patch("src.prepare_data.RAW_SHA256", checksum):
            prepare_dataset(self.raw_path, self.output)
            prepare_dataset(self.raw_path, self.output)
            prepare_dataset(self.raw_path, second_output)
            manifest = json.loads((self.output / "dataset_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["dataset_version"], DATASET_VERSION)
            self.assertEqual(manifest["raw"]["sha256"], checksum)
            for filename, expected_checksum in manifest["artifacts_sha256"].items():
                payload = (self.output / filename).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), expected_checksum)
                self.assertEqual(payload, (second_output / filename).read_bytes())
            altered = self.output / "games_main.csv"
            altered.write_text("external modification", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_dataset(self.raw_path, self.output)
            self.assertEqual(altered.read_text(encoding="utf-8"), "external modification")

    def test_rejects_unverified_raw_without_publishing_outputs(self):
        self.write_raw([game()])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            prepare_dataset(self.raw_path, self.output)
        self.assertFalse(self.output.exists())
