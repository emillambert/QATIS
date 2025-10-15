#!/usr/bin/env python3
import argparse
import csv
import pathlib
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        scheme = (parts.scheme or "").lower()
        netloc = (parts.netloc or "").lower()
        path = parts.path or ""
        # Drop trailing slash unless it's the only char
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]
        # Drop query and fragment to avoid UTM/etc noise
        return urlunsplit((scheme, netloc, path, "", ""))
    except Exception:
        return url.strip()


def find_duplicates(
    rows: Iterable[Dict[str, str]],
    key_field: str,
    normalize: bool,
) -> Tuple[Counter, Dict[str, List[int]]]:
    counts: Counter = Counter()
    indices: Dict[str, List[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        raw = (row.get(key_field) or "").strip()
        key = normalize_url(raw) if normalize else raw
        counts[key] += 1
        indices[key].append(idx + 2)  # +2 to account for header and 0-based index
    dupes = Counter({k: c for k, c in counts.items() if c > 1 and k})
    # Keep only duplicate indices
    dupe_indices = {k: v for k, v in indices.items() if k in dupes}
    return dupes, dupe_indices


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a CSV for duplicate rows by a given column")
    parser.add_argument("--input", required=True, help="Path to CSV to check")
    parser.add_argument("--on", default="link", help="Column name to de-duplicate on (default: link)")
    parser.add_argument("--normalize-url", action="store_true", help="Normalize URLs when comparing (lowercase host, drop query/fragment, trim trailing slash)")
    args = parser.parse_args()

    csv_path = pathlib.Path(args.input)
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]

    dupes, dupe_indices = find_duplicates(rows, args.on, args.normalize_url)

    total = sum(dupes.values())
    unique_dupe_keys = len(dupes)
    print(f"Duplicate check on {csv_path}")
    print(f"- Column: {args.on}")
    print(f"- Normalize URL: {bool(args.normalize_url)}")
    print(f"- Duplicate keys: {unique_dupe_keys}")
    if unique_dupe_keys:
        print(f"- Top duplicates (count :: key) -> first 20 shown:")
        for key, count in dupes.most_common(20):
            print(f"  {count:3d} :: {key}")
        print("\nLine numbers for each duplicate key (first 10 keys):")
        for i, (key, lines) in enumerate(dupe_indices.items()):
            if i >= 10:
                break
            print(f"- {key}: lines {lines}")
    else:
        print("No duplicates found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


