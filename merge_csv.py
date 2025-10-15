#!/usr/bin/env python3
import argparse
import csv
import pathlib
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


def read_csv_rows(path: pathlib.Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def split_to_set(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    # Support either semicolon or comma separated values
    tokens: List[str] = []
    for sep in [";", ","]:
        if sep in value:
            tokens = [t.strip() for t in value.split(sep)]
            break
    if not tokens:
        tokens = [value.strip()]
    return set([t for t in tokens if t])


def choose_first_non_empty(values: Iterable[Optional[str]]) -> Optional[str]:
    for v in values:
        if v is not None and str(v).strip() != "":
            return v
    return None


def merge_numeric_min(a: Optional[str], b: Optional[str]) -> Optional[int]:
    def to_int(x: Optional[str]) -> Optional[int]:
        try:
            return int(x) if x is not None and str(x).strip() != "" else None
        except Exception:
            return None

    ai = to_int(a)
    bi = to_int(b)
    if ai is None:
        return bi
    if bi is None:
        return ai
    return min(ai, bi)


def merge_numeric_max(a: Optional[str], b: Optional[str]) -> Optional[int]:
    def to_int(x: Optional[str]) -> Optional[int]:
        try:
            return int(x) if x is not None and str(x).strip() != "" else None
        except Exception:
            return None

    ai = to_int(a)
    bi = to_int(b)
    if ai is None:
        return bi
    if bi is None:
        return ai
    return max(ai, bi)


def merge_rows(
    existing: Dict[str, Any],
    incoming: Dict[str, Any],
    prefer: str,
) -> Dict[str, Any]:
    # Prefer can be 'first' or 'last'
    pick_order = (existing, incoming) if prefer == "first" else (incoming, existing)

    merged: Dict[str, Any] = dict(existing)

    # Merge known set-like fields by union
    for field in ["category", "query", "language", "engine"]:
        merged[field] = \
            "; ".join(sorted(split_to_set(existing.get(field)) | split_to_set(incoming.get(field)))) or None

    # Prefer the longer snippet
    current_snippet = str(existing.get("snippet") or "")
    new_snippet = str(incoming.get("snippet") or "")
    merged["snippet"] = new_snippet if len(new_snippet) > len(current_snippet) else current_snippet or None

    # Keep the smallest position seen
    merged["position"] = merge_numeric_min(existing.get("position"), incoming.get("position"))

    # Year bounds: min of mins, max of maxes
    merged["year_min"] = merge_numeric_min(existing.get("year_min"), incoming.get("year_min"))
    merged["year_max"] = merge_numeric_max(existing.get("year_max"), incoming.get("year_max"))

    # Occurrences: sum if both present and numeric
    def to_int_or_none(x: Any) -> Optional[int]:
        try:
            return int(x)
        except Exception:
            return None

    occ_a = to_int_or_none(existing.get("occurrences"))
    occ_b = to_int_or_none(incoming.get("occurrences"))
    if occ_a is not None or occ_b is not None:
        merged["occurrences"] = (occ_a or 0) + (occ_b or 0)

    # All other fields: choose first non-empty based on preference
    known_fields = {
        "category",
        "query",
        "language",
        "engine",
        "snippet",
        "position",
        "year_min",
        "year_max",
        "occurrences",
    }
    all_fields = set(existing.keys()) | set(incoming.keys())
    for field in all_fields - known_fields:
        if prefer == "first":
            merged[field] = choose_first_non_empty([existing.get(field), incoming.get(field)])
        else:
            merged[field] = choose_first_non_empty([incoming.get(field), existing.get(field)])

    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge two search CSVs and de-duplicate by a key (default: link)")
    parser.add_argument("--input-a", required=True, help="Path to first CSV (e.g., results_deduped.csv)")
    parser.add_argument("--input-b", required=True, help="Path to second CSV (e.g., general_results.csv)")
    parser.add_argument("--output", required=True, help="Path to write merged CSV")
    parser.add_argument("--dedupe-on", default="link", help="Column to use for de-duplication (default: link)")
    parser.add_argument("--prefer", choices=["first", "last"], default="first", help="Prefer fields from first or last when merging")
    args = parser.parse_args()

    input_a = pathlib.Path(args.input_a)
    input_b = pathlib.Path(args.input_b)
    output_path = pathlib.Path(args.output)

    rows_a, fields_a = read_csv_rows(input_a)
    rows_b, fields_b = read_csv_rows(input_b)

    # Union of fieldnames (preserve order: A then B extras)
    fieldnames: List[str] = list(fields_a)
    for f in fields_b:
        if f not in fieldnames:
            fieldnames.append(f)

    # Build merged map by dedupe key
    dedupe_key = args.dedupe_on
    merged_map: Dict[str, Dict[str, Any]] = {}

    def add_row(row: Dict[str, Any], prefer: str) -> None:
        key_raw = row.get(dedupe_key)
        key = str(key_raw).strip() if key_raw is not None else ""
        # Treat empty keys as unique rows (avoid accidental merges)
        if not key:
            synthetic_key = f"__nolink__::{row.get('title') or ''}::{row.get('engine') or ''}::{len(merged_map)}"
            merged_map[synthetic_key] = row
            return
        existing = merged_map.get(key)
        if existing is None:
            merged_map[key] = row
        else:
            merged_map[key] = merge_rows(existing, row, prefer)

    # Add rows from A then B
    for r in rows_a:
        add_row(r, args.prefer)
    for r in rows_b:
        add_row(r, args.prefer)

    # Write merged CSV
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for _k, row in merged_map.items():
            # Ensure all columns exist
            for col in fieldnames:
                row.setdefault(col, None)
            writer.writerow(row)

    print(f"Merged {len(rows_a)} + {len(rows_b)} rows -> {len(merged_map)} unique rows into {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


