"""Summarize data coverage and trace preparation decisions to the source."""

import pandas as pd


_REGIONAL_FIELDS = ("na_sales", "jp_sales", "pal_sales", "other_sales")
_DATE_FIELDS = ("release_date", "last_update")
_NUMERIC_FIELDS = ("critic_score", "total_sales", *_REGIONAL_FIELDS)
_PERIODS = ("before 2000", "2000-2018", "2019-2020", "2021+", "missing date")
_MAIN_DECISIONS = (
    "included",
    "exact_duplicate",
    "missing_or_invalid_release_date",
    "outside_main_window",
    "missing_or_invalid_total_sales",
    "missing_title_or_console",
)
_TRACE_COLUMNS = ["record_id", "source_row"]


def _field_missingness(raw: pd.DataFrame, audited: pd.DataFrame) -> pd.DataFrame:
    raw_missing = pd.Series(
        {field: raw[field].str.strip().eq("").sum() for field in raw}, dtype="int64"
    )
    audited_missing = audited.loc[:, raw.columns].isna().sum()
    summary = pd.DataFrame(
        {
            "input_records": len(raw),
            "raw_missing": raw_missing,
            "audited_missing": audited_missing,
            "invalid_nonblank": audited_missing - raw_missing,
        }
    )
    summary["raw_missing_rate"] = summary["raw_missing"].div(len(raw) or float("nan"))
    summary["audited_missing_rate"] = summary["audited_missing"].div(len(raw) or float("nan"))
    return summary.rename_axis("field").reset_index()


def _coverage_indicators(audited: pd.DataFrame) -> pd.DataFrame:
    dates = audited["release_date"].notna()
    totals = audited["total_sales"].notna()
    regional_fields = audited.loc[:, list(_REGIONAL_FIELDS)].notna()
    four_regions = regional_fields.all(axis=1)
    comparable = audited["regional_status"].eq("comparable")
    included = audited["main_exclusion"].eq("included")
    indicators = pd.DataFrame(
        {
            "records": 1,
            "release_date_available": dates,
            "total_sales_available": totals,
            "date_and_total_sales_available": dates & totals,
            "critic_score_available": audited["critic_score_observed"],
            "four_regions_available": four_regions,
            "total_and_four_regions_available": totals & four_regions,
            "regionally_comparable": comparable,
            "main_candidates": audited["in_main_window"] & dates & totals,
            "main_included": included,
            "main_regionally_comparable": included & comparable,
        }
    )
    return pd.concat([indicators, regional_fields.add_suffix("_available")], axis=1)


def _coverage_by(
    indicators: pd.DataFrame, groups: pd.Series, order: tuple[str, ...] = ()
) -> pd.DataFrame:
    summary = indicators.groupby(groups, dropna=False).sum().astype("int64")
    if order:
        summary = summary.reindex(order, fill_value=0)
    denominator = summary["records"].replace(0, float("nan"))
    summary["total_sales_coverage"] = summary["total_sales_available"].div(denominator)
    summary["four_regions_coverage"] = summary["four_regions_available"].div(denominator)
    return summary.rename_axis(groups.name).reset_index()


def _invalid_values(raw: pd.DataFrame, audited: pd.DataFrame) -> pd.DataFrame:
    records = []
    for field in (*_DATE_FIELDS, *_NUMERIC_FIELDS):
        invalid = raw[field].str.strip().ne("") & audited[field].isna()
        records.append(
            audited.loc[invalid, _TRACE_COLUMNS].assign(
                field=field, raw_value=raw.loc[invalid, field]
            )
        )
    return pd.concat(records).sort_values("source_row", kind="stable").reset_index(drop=True)


def build_audit_tables(raw: pd.DataFrame, audited: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return report tables keyed by CSV filename stem.

    The input and audited frames share row order and index. The input retains
    original CSV text, including empty strings and literal category labels.
    """
    if not raw.index.equals(audited.index):
        raise ValueError("The raw and audited data must have identical row indexes.")

    indicators = _coverage_indicators(audited)
    periods = (
        pd.cut(
            audited["release_year"],
            bins=[float("-inf"), 1999, 2018, 2020, float("inf")],
            labels=_PERIODS[:-1],
        )
        .cat.add_categories(["missing date"])
        .fillna("missing date")
        .rename("release_period")
    )

    decision_counts = audited["main_exclusion"].value_counts().reindex(_MAIN_DECISIONS, fill_value=0)
    ledger = decision_counts.rename_axis("main_exclusion").reset_index(name="records")
    ledger["input_records"] = len(audited)
    ledger["share_of_input"] = ledger["records"].div(len(audited) or float("nan"))

    conflict = audited["title_console_conflict"]
    conflict_metadata = audited.loc[
        conflict,
        [*_TRACE_COLUMNS, "title_group", "console_key", "exact_duplicate", "main_exclusion"],
    ]
    conflict_source = raw.loc[
        conflict,
        ["title", "console", "genre", "publisher", "developer", *_DATE_FIELDS, *_NUMERIC_FIELDS],
    ]
    conflict_details = pd.concat([conflict_metadata, conflict_source], axis=1)

    return {
        "field_missingness": _field_missingness(raw, audited),
        "coverage_by_year": _coverage_by(indicators, audited["release_year"]),
        "coverage_by_platform": _coverage_by(indicators, audited["console_key"].replace("", pd.NA)),
        "coverage_by_period": _coverage_by(indicators, periods, _PERIODS),
        "cleaning_ledger": ledger,
        "title_platform_conflicts": conflict_details,
        "invalid_values": _invalid_values(raw, audited),
    }
