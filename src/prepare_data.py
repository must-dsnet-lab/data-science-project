"""Prepare the pinned Kaggle Raw snapshot and publish a reproducible dataset."""

import argparse
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from src.data_audit import build_audit_tables

RAW_COLUMNS = (
    "img", "title", "console", "genre", "publisher", "developer", "critic_score",
    "total_sales", "na_sales", "jp_sales", "pal_sales", "other_sales", "release_date", "last_update",
)
RAW_FILENAME = "Video Games Sales (1980-2024) - Raw.csv"
RAW_SHA256 = "33780cc77d2395d82628c6f9120cc0905355a4804d5616dee06bdae414aff0d1"
DATASET_VERSION = "v1"
DATASET_URL = "https://www.kaggle.com/datasets/bhushandivekar/video-game-sales-and-industry-data-1980-2024"
MAIN_YEARS = (2000, 2018)
REGION_COLUMNS = ["na_sales", "jp_sales", "pal_sales", "other_sales"]
REGION_TOLERANCE = 0.025


def load_raw(raw_path: Path) -> tuple[pd.DataFrame, dict]:
    source = raw_path.read_bytes()
    checksum = hashlib.sha256(source).hexdigest()
    if checksum != RAW_SHA256:
        raise ValueError(
            f"Raw SHA-256 mismatch for {raw_path}. Expected {RAW_SHA256}; got {checksum}. "
            "Use the pinned Raw CSV without re-saving it in a spreadsheet editor."
        )
    raw = pd.read_csv(io.BytesIO(source), dtype="str", keep_default_na=False, encoding="utf-8-sig")
    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError("Raw CSV columns differ from the expected schema.")
    return raw, {
        "filename": RAW_FILENAME,
        "dataset_url": DATASET_URL,
        "publisher_account": "bhushandivekar",
        "sha256": checksum,
        "size_bytes": len(source),
        "rows": len(raw),
        "columns": list(RAW_COLUMNS),
    }


def key_for(values: pd.Series) -> pd.Series:
    return values.str.normalize("NFC").str.replace(r"\s+", " ", regex=True).str.casefold()


def build_audited(raw: pd.DataFrame) -> pd.DataFrame:
    audited = raw.apply(lambda column: column.str.strip().replace("", np.nan))
    for name in ["critic_score", "total_sales", *REGION_COLUMNS]:
        values = pd.to_numeric(audited[name], errors="coerce")
        valid = np.isfinite(values) & values.ge(0)
        if name == "critic_score":
            valid &= values.le(10)
        audited[name] = values.where(valid)
    for name in ["release_date", "last_update"]:
        values = audited[name]
        exact_format = values.str.fullmatch(r"[0-9]{2}-[0-9]{2}-[0-9]{4}", na=False)
        audited[name] = pd.to_datetime(values.where(exact_format), format="%d-%m-%Y", errors="coerce")

    audited.insert(0, "source_row", range(1, len(audited) + 1))
    audited.insert(0, "record_id", audited["source_row"].map("vgc-{:06d}".format))
    audited["title_group"] = key_for(audited["title"])
    audited["console_key"] = key_for(audited["console"])
    audited["release_year"] = audited["release_date"].dt.year.astype("Int64")
    audited["critic_score_observed"] = audited["critic_score"].notna()
    audited["publisher_suspect"] = audited["publisher"].eq("08-Apr")
    audited["exact_duplicate"] = raw.duplicated(keep="first")

    key_columns = ["title_group", "console_key"]
    has_key = audited[key_columns].notna().all(axis=1)
    keys = audited.loc[has_key & ~audited["exact_duplicate"], key_columns]
    repeated_keys = keys.loc[keys.duplicated(keep=False)]
    audited["title_console_conflict"] = pd.MultiIndex.from_frame(audited[key_columns]).isin(
        pd.MultiIndex.from_frame(repeated_keys)
    )
    audited["in_main_window"] = audited["release_year"].between(*MAIN_YEARS).fillna(False).astype(bool)
    audited["main_exclusion"] = np.select(
        [
            audited["exact_duplicate"],
            audited["release_date"].isna(),
            ~audited["in_main_window"],
            audited["total_sales"].isna(),
            ~has_key,
        ],
        [
            "exact_duplicate", "missing_or_invalid_release_date", "outside_main_window",
            "missing_or_invalid_total_sales", "missing_title_or_console",
        ],
        default="included",
    )

    regional_sum = audited[REGION_COLUMNS].sum(axis=1, min_count=len(REGION_COLUMNS))
    audited["region_total_delta"] = (regional_sum - audited["total_sales"]).round(10)
    audited["regional_status"] = np.select(
        [
            audited["region_total_delta"].isna(),
            audited["total_sales"].le(0),
            regional_sum.le(0),
            audited["region_total_delta"].abs().gt(REGION_TOLERANCE),
        ],
        ["missing_or_invalid_sales", "nonpositive_total", "nonpositive_regional_sum", "regional_total_mismatch"],
        default="comparable",
    )
    return audited


def write_outputs(raw: pd.DataFrame, metadata: dict, directory: Path) -> dict:
    audited = build_audited(raw)
    main = audited.loc[audited["main_exclusion"].eq("included")]
    tables = {"games_audited.csv": audited, "games_main.csv": main}
    tables.update({f"audit/{name}.csv": table for name, table in build_audit_tables(raw, audited).items()})
    (directory / "audit").mkdir()
    checksums = {}
    for name, table in tables.items():
        path = directory / name
        table.to_csv(path, index=False, lineterminator="\n", date_format="%Y-%m-%d", encoding="utf-8")
        checksums[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    dates = audited["release_date"].notna()
    totals = audited["total_sales"].notna()
    manifest = {
        "dataset_version": DATASET_VERSION,
        "raw": metadata,
        "main_release_years_inclusive": list(MAIN_YEARS),
        "sales_unit": "million copies",
        "regional_reconciliation_tolerance": REGION_TOLERANCE,
        "counts": {
            "audited": len(audited),
            "with_total_sales": int(totals.sum()),
            "with_date_and_total_sales": int((dates & totals).sum()),
            "main_candidates_before_record_checks": int((audited["in_main_window"] & totals).sum()),
            "main": len(main),
            "main_regional_comparable": int(main["regional_status"].eq("comparable").sum()),
            "main_with_observed_score": int(main["critic_score_observed"].sum()),
            "main_zero_total_sales": int(main["total_sales"].eq(0).sum()),
            "main_with_title_platform_candidates": int(main["title_console_conflict"].sum()),
        },
        "artifacts_sha256": checksums,
    }
    (directory / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def verify_existing_output(output_dir: Path, staged: Path) -> None:
    expected = {path.relative_to(staged) for path in staged.rglob("*") if path.is_file()}
    actual = {path.relative_to(output_dir) for path in output_dir.rglob("*") if path.is_file()}
    if expected == actual and all((output_dir / path).read_bytes() == (staged / path).read_bytes() for path in expected):
        return
    raise FileExistsError(f"Output differs from the rebuilt dataset: {output_dir}. Choose a new --output-dir.")


def prepare_dataset(raw_path: Path, output_dir: Path) -> dict:
    raw, metadata = load_raw(raw_path)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".prepare-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / "dataset"
        staged.mkdir()
        manifest = write_outputs(raw, metadata, staged)
        if output_dir.exists():
            verify_existing_output(output_dir, staged)
        else:
            try:
                staged.rename(output_dir)
            except OSError:
                if not output_dir.is_dir():
                    raise
                verify_existing_output(output_dir, staged)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path, help="Pinned Raw CSV downloaded from Kaggle")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    try:
        manifest = prepare_dataset(args.raw, args.output_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Data preparation failed: {error}\n")
    print(json.dumps({"output_dir": str(args.output_dir), **manifest["counts"]}, indent=2))


if __name__ == "__main__":
    main()
