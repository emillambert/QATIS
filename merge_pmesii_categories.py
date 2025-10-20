#!/usr/bin/env python3
"""
Merge all PMESII category results_scored.csv files into one master CSV.
Handles deduplication by link and preserves all AI classifications.
"""
import argparse
import csv
import pathlib
from typing import Any, Dict, List, Optional, Set


def split_to_set(value: Optional[str]) -> Set[str]:
    """Split semicolon or comma-separated string into set."""
    if not value:
        return set()
    tokens: List[str] = []
    for sep in [";", ","]:
        if sep in value:
            tokens = [t.strip() for t in value.split(sep)]
            break
    if not tokens:
        tokens = [value.strip()]
    return set([t for t in tokens if t])


def choose_first_non_empty(values: List[Optional[str]]) -> Optional[str]:
    """Return first non-empty value from list."""
    for v in values:
        if v is not None and str(v).strip() != "":
            return v
    return None


def merge_rows(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two rows, combining categories and preferring higher-confidence AI labels."""
    merged = dict(existing)
    
    # Merge category, query, language, engine by union
    for field in ["category", "query", "language", "engine"]:
        merged[field] = "; ".join(sorted(
            split_to_set(existing.get(field)) | split_to_set(incoming.get(field))
        )) or None
    
    # Merge PMESII tags by union
    if "pmesii" in existing or "pmesii" in incoming:
        merged["pmesii"] = "; ".join(sorted(
            split_to_set(existing.get("pmesii")) | split_to_set(incoming.get("pmesii"))
        )) or None
    
    # Prefer longer snippet
    current_snippet = str(existing.get("snippet") or "")
    new_snippet = str(incoming.get("snippet") or "")
    merged["snippet"] = new_snippet if len(new_snippet) > len(current_snippet) else current_snippet or None
    
    # Prefer longer full_content
    current_full = str(existing.get("full_content") or "")
    new_full = str(incoming.get("full_content") or "")
    merged["full_content"] = new_full if len(new_full) > len(current_full) else current_full or None
    
    # For AI classification fields, prefer the one with higher confidence
    try:
        existing_conf = float(existing.get("confidence", 0))
    except:
        existing_conf = 0.0
    try:
        incoming_conf = float(incoming.get("confidence", 0))
    except:
        incoming_conf = 0.0
    
    if incoming_conf > existing_conf:
        # Use incoming AI fields
        for field in ["label", "confidence", "source_type", 
                      "admiralty_source_reliability", "admiralty_distance_to_origin",
                      "admiralty_info_credibility", "rationale"]:
            if field in incoming:
                merged[field] = incoming[field]
    
    # Sum occurrences
    try:
        occ_a = int(existing.get("occurrences", 0))
    except:
        occ_a = 0
    try:
        occ_b = int(incoming.get("occurrences", 0))
    except:
        occ_b = 0
    if occ_a or occ_b:
        merged["occurrences"] = occ_a + occ_b
    
    # Keep smallest position
    try:
        pos_a = int(existing.get("position")) if existing.get("position") else None
    except:
        pos_a = None
    try:
        pos_b = int(incoming.get("position")) if incoming.get("position") else None
    except:
        pos_b = None
    if pos_a is None:
        merged["position"] = pos_b
    elif pos_b is None:
        merged["position"] = pos_a
    else:
        merged["position"] = min(pos_a, pos_b)
    
    # Keep year bounds
    for field in ["year_min", "year_max"]:
        merged[field] = choose_first_non_empty([existing.get(field), incoming.get(field)])
    
    # For all other fields, prefer existing
    all_fields = set(existing.keys()) | set(incoming.keys())
    known_fields = {
        "category", "query", "language", "engine", "snippet", "full_content",
        "pmesii", "position", "year_min", "year_max", "occurrences",
        "label", "confidence", "source_type", 
        "admiralty_source_reliability", "admiralty_distance_to_origin",
        "admiralty_info_credibility", "rationale"
    }
    for field in all_fields - known_fields:
        merged[field] = choose_first_non_empty([existing.get(field), incoming.get(field)])
    
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge PMESII category CSVs into master file")
    parser.add_argument("--pmesii-dir", required=True, help="PMESII exports directory (e.g., pmesii_exports/20251020_144507)")
    parser.add_argument("--output", required=True, help="Output merged CSV path")
    parser.add_argument("--include-non-intel", action="store_true", help="Include non-intel results (default: intel only)")
    args = parser.parse_args()
    
    pmesii_dir = pathlib.Path(args.pmesii_dir)
    categories = ["political", "military", "economic", "social", "information", "infrastructure"]
    
    merged_map: Dict[str, Dict[str, Any]] = {}
    all_fieldnames: Set[str] = set()
    
    for category in categories:
        if args.include_non_intel:
            csv_path = pmesii_dir / category / "results_scored.csv"
        else:
            csv_path = pmesii_dir / category / "results_scored_intel.csv"
        
        if not csv_path.exists():
            print(f"⚠️  Skipping {category}: {csv_path} not found")
            continue
        
        print(f"📂 Reading {category}...")
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                all_fieldnames.update(reader.fieldnames)
            
            for row in reader:
                link = (row.get("link") or "").strip()
                # Use link as dedupe key, or create synthetic key for non-link items
                if not link:
                    synthetic_key = f"__nolink__::{row.get('title') or ''}::{row.get('engine') or ''}::{len(merged_map)}"
                    merged_map[synthetic_key] = row
                    continue
                
                if link in merged_map:
                    merged_map[link] = merge_rows(merged_map[link], row)
                else:
                    merged_map[link] = row
    
    # Write merged output
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure standard field order
    standard_fields = [
        "category", "query", "language", "engine", "title", "link", 
        "source", "publication_info", "pdf_link", "date", "snippet", "full_content",
        "position", "year_min", "year_max", "occurrences",
        "label", "confidence", "pmesii", "source_type",
        "admiralty_source_reliability", "admiralty_distance_to_origin", 
        "admiralty_info_credibility", "rationale"
    ]
    # Add any extra fields from CSVs
    fieldnames = standard_fields + sorted(list(all_fieldnames - set(standard_fields)))
    
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for _k, row in merged_map.items():
            # Ensure all columns exist
            for col in fieldnames:
                row.setdefault(col, None)
            writer.writerow(row)
    
    print(f"\n✅ Merged {len(merged_map)} unique items into {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

