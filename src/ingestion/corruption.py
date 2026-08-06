from __future__ import annotations

import json
import math
import random
import string
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


CONTRACT_COLUMNS = (
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
    "updated",
    "age_days",
    "summary_chars",
    "text_for_embedding",
    "abs_url",
    "pdf_url",
)


def _coerce_rng(rng: random.Random | None, seed: int) -> random.Random:
    """Return a local RNG, never touching Python's global random state."""
    return rng if rng is not None else random.Random(seed)


def _normalise_target_ids(target_doc_ids: set[str] | None) -> set[str]:
    if not target_doc_ids:
        return set()
    return {str(paper_id) for paper_id in target_doc_ids}


def _paper_id(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _validate_ratio(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")


def _target_positions(
    df: pd.DataFrame,
    target_doc_ids: set[str],
    excluded_paper_ids: set[str],
) -> tuple[list[int], list[int]]:
    target_positions: list[int] = []
    other_positions: list[int] = []
    for position, value in enumerate(df["paper_id"].tolist()):
        paper_id = _paper_id(value)
        if paper_id in excluded_paper_ids:
            continue
        if paper_id in target_doc_ids:
            target_positions.append(position)
        else:
            other_positions.append(position)
    return target_positions, other_positions


def _select_positions(
    df: pd.DataFrame,
    count: int,
    rng: random.Random,
    target_doc_ids: set[str],
    excluded_paper_ids: Iterable[str] = (),
) -> list[int]:
    """Select rows with target documents first and random fallback."""
    if count <= 0 or df.empty:
        return []

    excluded = {str(paper_id) for paper_id in excluded_paper_ids}
    target_positions, other_positions = _target_positions(df, target_doc_ids, excluded)
    count = min(count, len(target_positions) + len(other_positions))

    selected_target = rng.sample(target_positions, min(count, len(target_positions)))
    remaining = count - len(selected_target)
    selected_other = rng.sample(other_positions, min(remaining, len(other_positions)))
    return selected_target + selected_other


def _count_for_ratio(ratio: float, row_count: int) -> int:
    if row_count <= 0 or ratio <= 0:
        return 0
    return min(row_count, max(1, math.ceil(ratio * row_count)))


def _drop_important_docs(
    df: pd.DataFrame,
    target_doc_ids: set[str] | None = None,
    *,
    ratio: float = 0.20,
    rng: random.Random | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Drop important documents, preferring rows in ``target_doc_ids``."""
    _validate_ratio("drop_ratio", ratio)
    result = df.copy(deep=True)
    if result.empty or ratio == 0:
        return result

    local_rng = _coerce_rng(rng, seed)
    target_ids = _normalise_target_ids(target_doc_ids)
    target_count = sum(_paper_id(value) in target_ids for value in result["paper_id"])
    basis_count = target_count if target_count else len(result)
    count = _count_for_ratio(ratio, basis_count)
    positions = _select_positions(result, count, local_rng, target_ids)
    if not positions:
        return result
    selected_positions = set(positions)
    kept_positions = [
        position for position in range(len(result)) if position not in selected_positions
    ]
    return result.iloc[kept_positions].copy()


def _blank_summary(
    df: pd.DataFrame,
    target_doc_ids: set[str] | None = None,
    *,
    ratio: float = 0.15,
    rng: random.Random | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Blank summaries on a target-prioritised subset of rows."""
    _validate_ratio("blank_ratio", ratio)
    result = df.copy(deep=True)
    if result.empty or ratio == 0:
        return result

    local_rng = _coerce_rng(rng, seed)
    positions = _select_positions(
        result,
        _count_for_ratio(ratio, len(result)),
        local_rng,
        _normalise_target_ids(target_doc_ids),
    )
    for position in positions:
        result.iat[position, result.columns.get_loc("summary")] = ""
    return result


def _inject_noise_summary(
    df: pd.DataFrame,
    target_doc_ids: set[str] | None = None,
    *,
    ratio: float = 0.15,
    rng: random.Random | None = None,
    seed: int = 42,
    excluded_paper_ids: Iterable[str] = (),
) -> pd.DataFrame:
    """Append deterministic noise to summaries not selected for blanking."""
    _validate_ratio("noise_ratio", ratio)
    result = df.copy(deep=True)
    if result.empty or ratio == 0:
        return result

    local_rng = _coerce_rng(rng, seed)
    positions = _select_positions(
        result,
        _count_for_ratio(ratio, len(result)),
        local_rng,
        _normalise_target_ids(target_doc_ids),
        excluded_paper_ids=excluded_paper_ids,
    )
    summary_column = result.columns.get_loc("summary")
    alphabet = string.ascii_letters + string.digits
    for position in positions:
        token = "".join(local_rng.choice(alphabet) for _ in range(16))
        original = _text(result.iat[position, summary_column])
        result.iat[position, summary_column] = (
            f"{original} [CORRUPTION_NOISE_{token}]"
        ).strip()
    return result


def _truncate_title(
    df: pd.DataFrame,
    target_doc_ids: set[str] | None = None,
    *,
    ratio: float = 0.15,
    length: int = 10,
    rng: random.Random | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Truncate titles without turning them into empty strings."""
    _validate_ratio("truncate_ratio", ratio)
    if length < 1:
        raise ValueError("title truncation length must be positive")
    result = df.copy(deep=True)
    if result.empty or ratio == 0:
        return result

    local_rng = _coerce_rng(rng, seed)
    positions = _select_positions(
        result,
        _count_for_ratio(ratio, len(result)),
        local_rng,
        _normalise_target_ids(target_doc_ids),
    )
    title_column = result.columns.get_loc("title")
    for position in positions:
        title = _text(result.iat[position, title_column])
        result.iat[position, title_column] = title[:length] or "?"
    return result


def _parse_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None
    parsed = pd.Timestamp(timestamp)
    if parsed.tzinfo is not None:
        parsed = parsed.tz_localize(None)
    return parsed


def _stale_value(value: Any, years: int) -> Any:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return value
    stale = parsed - pd.DateOffset(years=years)
    if isinstance(value, (pd.Timestamp, datetime)):
        return stale
    if isinstance(value, date) and not isinstance(value, datetime):
        return stale.date()
    return stale.date().isoformat()


def _stale_publication_date(
    df: pd.DataFrame,
    target_doc_ids: set[str] | None = None,
    *,
    ratio: float = 0.20,
    min_years: int = 3,
    max_years: int = 5,
    rng: random.Random | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Move publication and available update dates three to five years back."""
    _validate_ratio("stale_ratio", ratio)
    if min_years < 1 or max_years < min_years:
        raise ValueError("stale year bounds must satisfy 1 <= min_years <= max_years")
    result = df.copy(deep=True)
    if result.empty or ratio == 0:
        return result

    local_rng = _coerce_rng(rng, seed)
    positions = _select_positions(
        result,
        _count_for_ratio(ratio, len(result)),
        local_rng,
        _normalise_target_ids(target_doc_ids),
    )
    published_column = result.columns.get_loc("published")
    updated_column = result.columns.get_loc("updated")
    for position in positions:
        years = local_rng.randint(min_years, max_years)
        result.iat[position, published_column] = _stale_value(
            result.iat[position, published_column], years
        )
        updated = result.iat[position, updated_column]
        if _text(updated).strip():
            result.iat[position, updated_column] = _stale_value(updated, years)
    return result


def _duplicate_id(base_id: str, existing_ids: set[str]) -> str:
    candidate = f"{base_id}-dup"
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base_id}-dup-{suffix}"
        suffix += 1
    return candidate


def _add_duplicate_rows(
    df: pd.DataFrame,
    target_doc_ids: set[str] | None = None,
    *,
    ratio: float = 0.10,
    minimum: int = 2,
    rng: random.Random | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Append duplicate rows with a ``-dup`` paper ID suffix."""
    _validate_ratio("duplicate_ratio", ratio)
    if minimum < 1:
        raise ValueError("minimum duplicate count must be positive")
    result = df.copy(deep=True)
    if result.empty or ratio == 0:
        return result

    local_rng = _coerce_rng(rng, seed)
    count = max(minimum, math.ceil(ratio * len(result)))
    positions = _select_positions(
        result,
        min(count, len(result)),
        local_rng,
        _normalise_target_ids(target_doc_ids),
    )
    if not positions:
        return result

    if len(positions) < count:
        target_positions, other_positions = _target_positions(
            result,
            _normalise_target_ids(target_doc_ids),
            set(),
        )
        repeat_pool = target_positions or other_positions
        positions.extend(
            local_rng.choice(repeat_pool) for _ in range(count - len(positions))
        )

    existing_ids = {_paper_id(value) for value in result["paper_id"]}
    duplicate_rows: list[pd.Series] = []
    for position in positions:
        row = result.iloc[position].copy(deep=True)
        original_id = _paper_id(row["paper_id"])
        duplicate_id = _duplicate_id(original_id, existing_ids)
        row["paper_id"] = duplicate_id
        existing_ids.add(duplicate_id)
        duplicate_rows.append(row)
    duplicates = pd.DataFrame(duplicate_rows, columns=result.columns)
    return pd.concat([result, duplicates], ignore_index=True)


def _reference_date(df: pd.DataFrame) -> pd.Timestamp:
    """Recover the cleaning run date from existing ``published`` and ``age_days``.

    The clean DataFrame persists age in days but not its run date. Reconstructing
    that date keeps the corruption result stable across calendar days while using
    the same convention as cleaning: ``age_days = run_date - published``.
    """
    candidates: list[pd.Timestamp] = []
    for published, age_days in zip(
        df["published"].tolist(),
        df["age_days"].tolist(),
        strict=False,
    ):
        published_date = _parse_timestamp(published)
        if published_date is None:
            continue
        try:
            if pd.isna(age_days):
                continue
            age = int(age_days)
        except (TypeError, ValueError):
            continue
        candidates.append(published_date.normalize() + pd.Timedelta(days=age))

    if candidates:
        frequencies = Counter(candidates)
        highest_frequency = max(frequencies.values())
        return max(
            candidate
            for candidate, frequency in frequencies.items()
            if frequency == highest_frequency
        )

    published_dates = [
        parsed for value in df["published"].tolist()
        if (parsed := _parse_timestamp(value)) is not None
    ]
    return max(published_dates, default=pd.Timestamp("1970-01-01")).normalize()


def _compute_age_days(value: Any, reference_date: pd.Timestamp) -> int | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return int((reference_date - parsed.normalize()).days)


def _build_text_for_embedding(row: pd.Series) -> str:
    """Build the title/summary/author/category text used by the embedding stage."""
    # cleaning.py is currently a TODO, so keep this local formula aligned with
    # Guide.md step 4 until that module exposes a shared public helper.
    return "\n".join(
        (
            f"Title: {_text(row['title'])}",
            f"Summary: {_text(row['summary'])}",
            f"Authors: {_text(row['authors_joined'])}",
            f"Categories: {_text(row['categories_joined'])}",
        )
    )


def _rebuild_derived_columns(
    df: pd.DataFrame,
    reference_date: pd.Timestamp,
) -> pd.DataFrame:
    result = df.copy(deep=True)
    result["summary_chars"] = result["summary"].map(lambda value: len(_text(value)))
    result["age_days"] = result["published"].map(
        lambda value: _compute_age_days(value, reference_date)
    )
    result["text_for_embedding"] = result.apply(
        _build_text_for_embedding,
        axis=1,
    )
    return result


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        missing = False
    if isinstance(missing, bool) and missing:
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return _json_value(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _row_snapshots(
    df: pd.DataFrame,
    paper_ids: Iterable[str],
    fields: Iterable[str],
) -> dict[str, dict[str, Any]]:
    wanted = list(fields)
    if wanted == ["row"]:
        wanted = list(df.columns)
    snapshots: dict[str, dict[str, Any]] = {}
    requested = list(paper_ids)
    for _, row in df.iterrows():
        paper_id = _paper_id(row["paper_id"])
        if paper_id in requested and paper_id not in snapshots:
            snapshots[paper_id] = {
                field: _json_value(row[field]) for field in wanted if field in row
            }
    return {paper_id: snapshots[paper_id] for paper_id in requested if paper_id in snapshots}


def _values_differ(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return False
    try:
        left_missing = pd.isna(left)
        right_missing = pd.isna(right)
        if isinstance(left_missing, bool) and isinstance(right_missing, bool):
            if left_missing and right_missing:
                return False
            if left_missing != right_missing:
                return True
    except (TypeError, ValueError):
        pass
    return left != right


def _changed_ids(
    before: pd.DataFrame,
    after: pd.DataFrame,
    fields: Iterable[str],
) -> list[str]:
    field_names = list(fields)
    before_rows = {
        _paper_id(row["paper_id"]): row for _, row in before.iterrows()
    }
    after_rows = {
        _paper_id(row["paper_id"]): row for _, row in after.iterrows()
    }
    changed: list[str] = []
    for paper_id, before_row in before_rows.items():
        after_row = after_rows.get(paper_id)
        if after_row is None:
            changed.append(paper_id)
            continue
        if any(
            _values_differ(before_row[field], after_row[field])
            for field in field_names
            if field in before_row and field in after_row
        ):
            changed.append(paper_id)
    return changed


def _ordered_ids(
    paper_ids: Iterable[str],
    before: pd.DataFrame,
    target_doc_ids: set[str],
) -> list[str]:
    requested = set(paper_ids)
    ordered = [
        _paper_id(value)
        for value in before["paper_id"].tolist()
        if _paper_id(value) in requested
    ]
    target_first = [paper_id for paper_id in ordered if paper_id in target_doc_ids]
    others = [paper_id for paper_id in ordered if paper_id not in target_doc_ids]
    result: list[str] = []
    for paper_id in target_first + others:
        if paper_id not in result:
            result.append(paper_id)
    return result


def _scenario_record(
    scenario: str,
    seed: int,
    before: pd.DataFrame,
    after: pd.DataFrame,
    fields: list[str],
    target_doc_ids: set[str],
) -> dict[str, Any]:
    changed = _ordered_ids(_changed_ids(before, after, fields), before, target_doc_ids)
    return {
        "scenario": scenario,
        "seed": seed,
        "row_count_before": len(before),
        "row_count_after": len(after),
        "affected_paper_ids": changed,
        "fields_changed": fields,
        "before": _row_snapshots(before, changed, fields),
        "after": _row_snapshots(after, changed, fields),
    }


def _duplicate_scenario_record(
    seed: int,
    before: pd.DataFrame,
    after: pd.DataFrame,
    target_doc_ids: set[str],
) -> dict[str, Any]:
    before_ids = {_paper_id(value) for value in before["paper_id"]}
    duplicate_ids = [
        _paper_id(value)
        for value in after["paper_id"]
        if _paper_id(value) not in before_ids and "-dup" in _paper_id(value)
    ]
    source_ids = [paper_id.split("-dup", 1)[0] for paper_id in duplicate_ids]
    ordered_sources = _ordered_ids(source_ids, before, target_doc_ids)
    ordered_duplicates: list[str] = []
    for source_id in ordered_sources:
        ordered_duplicates.extend(
            duplicate_id
            for duplicate_id in duplicate_ids
            if duplicate_id.split("-dup", 1)[0] == source_id
        )
    affected = ordered_sources + ordered_duplicates
    return {
        "scenario": "add_duplicate_rows",
        "seed": seed,
        "row_count_before": len(before),
        "row_count_after": len(after),
        "affected_paper_ids": affected,
        "fields_changed": ["paper_id"],
        "before": _row_snapshots(before, ordered_sources, ["paper_id"]),
        "after": _row_snapshots(after, ordered_duplicates, ["paper_id"]),
    }


def _write_log(path: str | Path, records: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path: str | Path,
    target_doc_ids: set[str] | None = None,
    seed: int = 42,
    *,
    drop_ratio: float = 0.20,
    blank_ratio: float = 0.15,
    noise_ratio: float = 0.15,
    truncate_ratio: float = 0.15,
    title_length: int = 10,
    stale_ratio: float = 0.20,
    stale_min_years: int = 3,
    stale_max_years: int = 5,
    duplicate_ratio: float = 0.10,
    duplicate_min_rows: int = 2,
) -> pd.DataFrame:
    """Return a corrupted copy of ``df`` and write a JSON corruption log."""
    missing_columns = [column for column in CONTRACT_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"DataFrame is missing contract columns: {missing_columns}")
    for name, ratio in (
        ("drop_ratio", drop_ratio),
        ("blank_ratio", blank_ratio),
        ("noise_ratio", noise_ratio),
        ("truncate_ratio", truncate_ratio),
        ("stale_ratio", stale_ratio),
        ("duplicate_ratio", duplicate_ratio),
    ):
        _validate_ratio(name, ratio)
    if title_length < 1:
        raise ValueError("title_length must be positive")
    if duplicate_min_rows < 1:
        raise ValueError("duplicate_min_rows must be positive")
    if stale_min_years < 1 or stale_max_years < stale_min_years:
        raise ValueError(
            "stale year bounds must satisfy 1 <= stale_min_years <= stale_max_years"
        )

    target_ids = _normalise_target_ids(target_doc_ids)
    result = df.copy(deep=True)
    row_count_before = len(result)
    reference_date = _reference_date(result)
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []

    before = result.copy(deep=True)
    result = _drop_important_docs(
        result,
        target_ids,
        ratio=drop_ratio,
        rng=rng,
    )
    records.append(
        _scenario_record(
            "drop_important_docs",
            seed,
            before,
            result,
            ["row"],
            target_ids,
        )
    )

    before = result.copy(deep=True)
    result = _blank_summary(
        result,
        target_ids,
        ratio=blank_ratio,
        rng=rng,
    )
    blank_ids = _changed_ids(before, result, ["summary"])
    records.append(
        _scenario_record(
            "blank_summary",
            seed,
            before,
            result,
            ["summary"],
            target_ids,
        )
    )

    before = result.copy(deep=True)
    result = _inject_noise_summary(
        result,
        target_ids,
        ratio=noise_ratio,
        rng=rng,
        excluded_paper_ids=blank_ids,
    )
    records.append(
        _scenario_record(
            "inject_noise_summary",
            seed,
            before,
            result,
            ["summary"],
            target_ids,
        )
    )

    before = result.copy(deep=True)
    result = _truncate_title(
        result,
        target_ids,
        ratio=truncate_ratio,
        length=title_length,
        rng=rng,
    )
    records.append(
        _scenario_record(
            "truncate_title",
            seed,
            before,
            result,
            ["title"],
            target_ids,
        )
    )

    before = result.copy(deep=True)
    result = _stale_publication_date(
        result,
        target_ids,
        ratio=stale_ratio,
        min_years=stale_min_years,
        max_years=stale_max_years,
        rng=rng,
    )
    stale_fields = ["published"]
    if "updated" in result.columns and any(
        _text(value).strip() for value in before["updated"].tolist()
    ):
        stale_fields.append("updated")
    records.append(
        _scenario_record(
            "stale_publication_date",
            seed,
            before,
            result,
            stale_fields,
            target_ids,
        )
    )

    before = result.copy(deep=True)
    result = _add_duplicate_rows(
        result,
        target_ids,
        ratio=duplicate_ratio,
        minimum=duplicate_min_rows,
        rng=rng,
    )
    records.append(_duplicate_scenario_record(seed, before, result, target_ids))

    result = _rebuild_derived_columns(result, reference_date)
    affected_ids: list[str] = []
    for record in records:
        for paper_id in record["affected_paper_ids"]:
            if paper_id not in affected_ids:
                affected_ids.append(paper_id)
    records.append(
        {
            "scenario": "summary",
            "seed": seed,
            "row_count_before": row_count_before,
            "row_count_after": len(result),
            "affected_paper_ids": affected_ids,
            "fields_changed": [
                field
                for field in ("row", "summary", "title", "published", "updated", "paper_id")
                if any(field in record["fields_changed"] for record in records)
            ],
            "before": {},
            "after": {},
        }
    )
    _write_log(output_log_path, records)
    return result
