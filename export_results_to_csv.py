#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
from typing import Any, Dict, List, Optional


def load_index(index_path: pathlib.Path) -> List[Dict[str, Any]]:
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entries", [])


def load_entry_json(path: pathlib.Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate search JSON results into a CSV")
    parser.add_argument("--results-dir", required=True, help="A specific timestamped results directory, e.g. search_results/20251015_001826")
    parser.add_argument("--output", default="results.csv", help="CSV output filename")
    parser.add_argument("--dedupe", action="store_true", help="Merge rows with the same link (union categories/queries/languages/engines)")
    args = parser.parse_args()

    results_dir = pathlib.Path(args.results_dir)
    index_path = results_dir / "index.json"
    entries = load_index(index_path)

    rows: List[Dict[str, Any]] = []
    for entry in entries:
        category = entry.get("category")
        query = entry.get("query")
        language = entry.get("language")
        json_path = pathlib.Path(entry.get("json"))
        payload = load_entry_json(json_path)
        year_min = payload.get("year_min")
        year_max = payload.get("year_max")
        results = payload.get("results", {})

        for engine, items in results.items():
            for item in items:
                rows.append(
                    {
                        "category": category,
                        "query": query,
                        "language": language,
                        "engine": engine,
                        "title": item.get("title"),
                        "link": item.get("link"),
                        "source": item.get("source"),
                        "publication_info": item.get("publication_info"),
                        "pdf_link": item.get("pdf_link"),
                        "date": item.get("date"),
                        "snippet": item.get("snippet"),
                        "position": item.get("position"),
                        "year_min": year_min,
                        "year_max": year_max,
                    }
                )

    # Optionally de-duplicate by link
    if args.dedupe:
        def choose_first_non_empty(values: List[Optional[str]]) -> Optional[str]:
            for v in values:
                if v:
                    return v
            return None

        merged: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            link = (r.get("link") or "").strip()
            if not link:
                # Keep non-link rows distinct by using a synthetic key
                link = f"__nolink__::{r.get('title') or ''}::{r.get('engine') or ''}"
            bucket = merged.get(link)
            if not bucket:
                merged[link] = {
                    "category": set([r.get("category")]) if r.get("category") else set(),
                    "query": set([r.get("query")]) if r.get("query") else set(),
                    "language": set([r.get("language")]) if r.get("language") else set(),
                    "engine": set([r.get("engine")]) if r.get("engine") else set(),
                    "title": r.get("title"),
                    "link": r.get("link"),
                    "source": r.get("source"),
                    "publication_info": r.get("publication_info"),
                    "pdf_link": r.get("pdf_link"),
                    "date": r.get("date"),
                    "snippet": r.get("snippet"),
                    "position": r.get("position"),
                    "year_min": r.get("year_min"),
                    "year_max": r.get("year_max"),
                    "occurrences": 1,
                }
            else:
                bucket["category"].update([r.get("category")] if r.get("category") else [])
                bucket["query"].update([r.get("query")] if r.get("query") else [])
                bucket["language"].update([r.get("language")] if r.get("language") else [])
                bucket["engine"].update([r.get("engine")] if r.get("engine") else [])
                bucket["title"] = choose_first_non_empty([bucket.get("title"), r.get("title")])
                bucket["source"] = choose_first_non_empty([bucket.get("source"), r.get("source")])
                bucket["publication_info"] = choose_first_non_empty([bucket.get("publication_info"), r.get("publication_info")])
                bucket["pdf_link"] = choose_first_non_empty([bucket.get("pdf_link"), r.get("pdf_link")])
                bucket["date"] = choose_first_non_empty([bucket.get("date"), r.get("date")])
                # Prefer the longest snippet for richness
                current_snip = bucket.get("snippet") or ""
                new_snip = r.get("snippet") or ""
                bucket["snippet"] = new_snip if len(new_snip) > len(current_snip) else current_snip
                # Keep the smallest position seen
                try:
                    current_pos = int(bucket.get("position")) if bucket.get("position") is not None else None
                except Exception:
                    current_pos = None
                try:
                    new_pos = int(r.get("position")) if r.get("position") is not None else None
                except Exception:
                    new_pos = None
                if current_pos is None or (new_pos is not None and new_pos < current_pos):
                    bucket["position"] = new_pos
                # Keep year bounds if present; prefer min of mins and max of maxes
                try:
                    ym = int(bucket.get("year_min")) if bucket.get("year_min") is not None else None
                except Exception:
                    ym = None
                try:
                    y2 = int(r.get("year_min")) if r.get("year_min") is not None else None
                except Exception:
                    y2 = None
                bucket["year_min"] = min([v for v in [ym, y2] if v is not None]) if any(v is not None for v in [ym, y2]) else None
                try:
                    yM = int(bucket.get("year_max")) if bucket.get("year_max") is not None else None
                except Exception:
                    yM = None
                try:
                    y3 = int(r.get("year_max")) if r.get("year_max") is not None else None
                except Exception:
                    y3 = None
                bucket["year_max"] = max([v for v in [yM, y3] if v is not None]) if any(v is not None for v in [yM, y3]) else None
                bucket["occurrences"] = int(bucket.get("occurrences", 1)) + 1

        # Convert sets to sorted, joined strings
        deduped_rows: List[Dict[str, Any]] = []
        for _k, b in merged.items():
            deduped_rows.append(
                {
                    "category": "; ".join(sorted([x for x in b["category"] if x])) or None,
                    "query": "; ".join(sorted([x for x in b["query"] if x])) or None,
                    "language": "; ".join(sorted([x for x in b["language"] if x])) or None,
                    "engine": "; ".join(sorted([x for x in b["engine"] if x])) or None,
                    "title": b.get("title"),
                    "link": b.get("link"),
                    "source": b.get("source"),
                    "publication_info": b.get("publication_info"),
                    "pdf_link": b.get("pdf_link"),
                    "date": b.get("date"),
                    "snippet": b.get("snippet"),
                    "position": b.get("position"),
                    "year_min": b.get("year_min"),
                    "year_max": b.get("year_max"),
                    "occurrences": b.get("occurrences", 1),
                }
            )
        rows = deduped_rows

    fieldnames = [
        "category",
        "query",
        "language",
        "engine",
        "title",
        "link",
        "source",
        "publication_info",
        "pdf_link",
        "date",
        "snippet",
        "position",
        "year_min",
        "year_max",
        "occurrences",
    ]

    out_path = results_dir / args.output
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


