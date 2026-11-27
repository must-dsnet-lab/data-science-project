"""Compare archived Cleaned scores with matching observations in Raw."""

import argparse
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from statistics import median


SHARED_FIELDS = ("title", "console", "genre", "publisher", "developer", "total_sales")
SCORE_FIELD = "critic_score"
REPEATED_SCORE = Decimal("7.3")


def read_csv(path, required_fields):
    contents = path.read_bytes()
    source = StringIO(contents.decode("utf-8-sig"), newline="")
    reader = csv.DictReader(source, strict=True)
    headers = reader.fieldnames or []
    if len(set(headers)) != len(headers):
        raise ValueError(f"{path.name}: duplicate CSV column names")
    missing = sorted(set(required_fields) - set(headers))
    if missing:
        raise ValueError(f"{path.name}: missing columns: {', '.join(missing)}")

    rows = []
    for row in reader:
        if None in row or None in row.values():
            raise ValueError(f"{path.name}: file line {reader.line_num} has the wrong field count")
        rows.append(row)
    metadata = {"file": path.name, "sha256": sha256(contents).hexdigest(), "rows": len(rows)}
    return rows, metadata


def parse_number(value):
    if not value:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"non-finite numeric value: {value!r}")
    return number


def raw_profile(row):
    release_year = datetime.strptime(row["release_date"], "%d-%m-%Y").year
    return (
        row["title"],
        row["console"],
        row["genre"],
        row["publisher"],
        row["developer"] or "Unknown",
        parse_number(row["total_sales"]),
        release_year,
    )


def cleaned_profile(row):
    return (
        row["title"],
        row["console"],
        row["genre"],
        row["publisher"],
        row["developer"],
        parse_number(row["total_sales"]),
        parse_number(row["release_year"]),
    )


def audit_score_reference(raw_path, reference_path):
    raw_rows, raw_metadata = read_csv(raw_path, (*SHARED_FIELDS, SCORE_FIELD, "release_date"))
    cleaned_rows, cleaned_metadata = read_csv(
        reference_path, (*SHARED_FIELDS, SCORE_FIELD, "release_year")
    )
    eligible = [
        (source_row, row)
        for source_row, row in enumerate(raw_rows, start=1)
        if row["release_date"] and row["total_sales"]
    ]
    if not eligible or len(eligible) != len(cleaned_rows):
        raise ValueError(
            f"cannot pair {len(eligible):,} eligible Raw rows with {len(cleaned_rows):,} Cleaned rows"
        )

    original_scores = []
    scores_where_raw_was_missing = []
    changed_scores = 0
    developer_replacements = 0
    profiles = Counter()
    for reference_row, ((source_row, raw), cleaned) in enumerate(
        zip(eligible, cleaned_rows, strict=True), start=1
    ):
        expected = raw_profile(raw)
        actual = cleaned_profile(cleaned)
        for field, left, right in zip((*SHARED_FIELDS, "release_year"), expected, actual, strict=True):
            if left != right:
                raise ValueError(
                    f"shared field {field!r} differs at Raw row {source_row:,} "
                    f"and Cleaned row {reference_row:,}. Check the input versions and row order."
                )
        profiles[expected] += 1
        developer_replacements += not raw["developer"]

        original_score = parse_number(raw[SCORE_FIELD])
        cleaned_score = parse_number(cleaned[SCORE_FIELD])
        if original_score is None:
            scores_where_raw_was_missing.append(cleaned_score)
        else:
            original_scores.append(original_score)
            changed_scores += cleaned_score != original_score

    raw_median = median(original_scores) if original_scores else None
    filled_counts = Counter(scores_where_raw_was_missing)
    reference_scores = [parse_number(row[SCORE_FIELD]) for row in cleaned_rows]
    return {
        "raw": raw_metadata,
        "cleaned_reference": cleaned_metadata,
        "pairing": "Eligible Raw rows in source order, with all shared fields checked before score comparison",
        "paired_rows": len(eligible),
        "non_unique_shared_field_profiles": sum(count > 1 for count in profiles.values()),
        "developer_blanks_replaced_with_unknown": developer_replacements,
        "raw_observed_scores": len(original_scores),
        "raw_missing_scores": len(scores_where_raw_was_missing),
        "raw_observed_median": float(raw_median) if raw_median is not None else None,
        "raw_observed_7_3": original_scores.count(REPEATED_SCORE),
        "cleaned_7_3": reference_scores.count(REPEATED_SCORE),
        "observed_scores_changed": changed_scores,
        "raw_missing_scores_left_blank": filled_counts[None],
        "fill_value_counts": {
            format(value.normalize(), "f"): count
            for value, count in sorted(
                (value, count) for value, count in filled_counts.items() if value is not None
            )
        },
        "missing_scores_filled_with_raw_median": filled_counts[raw_median] if raw_median is not None else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True, help="Original Kaggle Raw CSV")
    parser.add_argument("--cleaned-reference", type=Path, required=True, help="Archived Cleaned CSV")
    args = parser.parse_args()
    try:
        summary = audit_score_reference(args.raw, args.cleaned_reference)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, f"Score reference audit failed: {exc}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
