#!/usr/bin/env python3
import argparse
import csv
import pathlib
import re
from typing import Dict, Iterable, List, Optional, Tuple


def read_scored_csv(path: pathlib.Path) -> Iterable[Dict[str, str]]:

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def parse_year(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    # Accept YYYY or ISO/date-like strings; take first 4-digit year between 1900-2099
    m = re.search(r"\b(19\d{2}|20\d{2})\b", str(value))
    return m.group(1) if m else None


def normalize_key(s: str) -> str:
    # Create a simple BibTeX key: first author/org token + year + short slug of title
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "ref"


def build_bib_entry(
    title: str,
    url: Optional[str],
    year: Optional[str],
    organization: Optional[str],
    key_hint: Optional[str] = None,
) -> Tuple[str, str]:
    # Choose key from organization or title + year
    base_for_key = (organization or title or "reference").strip()
    key_parts = [normalize_key(base_for_key)]
    if year:
        key_parts.append(year)
    key = "-".join([p for p in key_parts if p])
    if key_hint:
        key = normalize_key(key_hint)

    # Minimal, robust @misc entry
    fields: List[Tuple[str, str]] = []
    if title:
        fields.append(("title", title))
    if organization:
        fields.append(("organization", organization))
    if year:
        fields.append(("year", year))
    if url:
        fields.append(("url", url))

    body_lines = []
    for k, v in fields:
        # Escape braces in values minimally to keep BibTeX stable
        safe = v.replace("{", "\\{").replace("}", "\\}")
        body_lines.append(f"  {k} = {{{safe}}},")
    body = "\n".join(body_lines)
    entry = f"@misc{{{key},\n{body}\n}}\n"
    return key, entry


def generate_bib(
    rows: Iterable[Dict[str, str]],
    intel_only: bool = True,
    dedupe_on: str = "link",
) -> List[str]:
    seen: set = set()
    entries: List[str] = []
    for row in rows:
        if intel_only and str(row.get("label", "")).strip().lower() != "intel":
            continue

        link = (row.get(dedupe_on) or "").strip()
        if link and link in seen:
            continue

        title = (row.get("title") or "").strip()
        url = (row.get("link") or "").strip() or None
        # Prefer explicit year if present, otherwise parse from date
        explicit_year = (row.get("year") or "").strip() or None
        date_field = (row.get("date") or "").strip() or None
        year = explicit_year or parse_year(date_field)

        # Organization/source preference: publication_info first, then source
        organization = (row.get("publication_info") or "").strip()
        if not organization:
            organization = (row.get("source") or "").strip()
        if not title and organization and date_field:
            # Fallback synthesized title if missing
            title = f"{organization} report ({date_field})"
        if not title:
            title = "Untitled"

        key_hint = None
        if organization and year:
            key_hint = f"{organization}-{year}"
        key, entry = build_bib_entry(title=title, url=url, year=year, organization=organization, key_hint=key_hint)
        entries.append(entry)

        if link:
            seen.add(link)

    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate BibTeX from results_scored.csv")
    parser.add_argument("--input", required=True, help="Path to results_scored.csv (or scored CSV)")
    parser.add_argument("--output", default="intel_sources.bib", help="Output .bib filename")
    parser.add_argument("--all", action="store_true", help="Include non-intel rows as well")
    parser.add_argument("--dedupe-on", default="link", help="Column to use for deduplication (default: link)")
    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    out_path = input_path.parent / args.output

    rows = list(read_scored_csv(input_path))
    entries = generate_bib(rows, intel_only=(not args.all), dedupe_on=args.dedupe_on)

    with open(out_path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(e)

    print(f"Wrote {len(entries)} entries to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



