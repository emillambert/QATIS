#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import os
from importlib import resources as ilres
import pathlib
import re
import time
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
try:
    # Optional: used for prompt precedence
    from qatis.config import PROMPTS_DIR as QATIS_PROMPTS_DIR
except Exception:
    QATIS_PROMPTS_DIR = None
from openai import OpenAI
from slugify import slugify
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
from tqdm import tqdm

try:
    import trafilatura
except Exception:  # optional
    trafilatura = None


@dataclass
class Row:
    category: Optional[str]
    query: Optional[str]
    language: Optional[str]
    engine: Optional[str]
    title: Optional[str]
    link: Optional[str]
    source: Optional[str]
    publication_info: Optional[str]
    pdf_link: Optional[str]
    date: Optional[str]
    snippet: Optional[str]
    full_content: Optional[str]  # NEW: Enhanced content for social media
    position: Optional[str]
    year_min: Optional[str]
    year_max: Optional[str]
    occurrences: Optional[str]


def load_rows(csv_path: pathlib.Path, limit: Optional[int] = None) -> List[Row]:
    rows: List[Row] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for i, rec in enumerate(r):
            rows.append(Row(**{k: rec.get(k) for k in r.fieldnames}))
            if limit and len(rows) >= limit:
                break
    return rows


def normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    u = url.strip()
    u = re.sub(r"#.*$", "", u)  # remove anchors
    u = re.sub(r"[?&]utm_[^=&]+=[^&]+", "", u)  # remove utm params
    u = re.sub(r"[?&]fbclid=[^&]+", "", u)
    # canonicalize duplicate ?& leftovers
    u = re.sub(r"\?&", "?", u)
    u = u.rstrip("?&")
    return u


def dedupe_rows(rows: List[Row]) -> List[Row]:
    """Remove duplicate items by normalized URL; for rows without URLs, fall back to title+engine key.

    This is a safety net in case a non-deduped CSV is provided. The exporter already
    supports --dedupe, but we ensure uniqueness here before calling the LLM.
    """
    seen_keys = set()
    unique_rows: List[Row] = []
    for row in rows:
        norm = normalize_url(row.link)
        key = norm or f"__nolink__::{(row.title or '').strip()}::{(row.engine or '').strip()}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_rows.append(row)
    return unique_rows


def read_prompt(prompt_path: pathlib.Path) -> str:
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def load_system_prompt(results_dir: pathlib.Path) -> str:
    """Resolve analysis prompt with precedence:
    1) results_dir/custom_analyze_prompt.md
    2) ~/.qatis/prompts/custom.md
    3) packaged qatis/prompts/analyze_instruction.md
    4) project prompts/analyze_instruction.md (fallback)
    """
    # 1) results_dir override
    override = results_dir / "custom_analyze_prompt.md"
    if override.exists():
        try:
            return override.read_text(encoding="utf-8")
        except Exception:
            pass

    # 2) user custom prompt
    try:
        if QATIS_PROMPTS_DIR is not None:
            custom = QATIS_PROMPTS_DIR / "custom.md"
            if custom.exists():
                return custom.read_text(encoding="utf-8")
    except Exception:
        pass

    # 3) packaged default
    try:
        pkg_prompt = ilres.files("qatis").joinpath("prompts/analyze_instruction.md")
        return pkg_prompt.read_text(encoding="utf-8")
    except Exception:
        pass

    # 4) project fallback
    proj = pathlib.Path("prompts/analyze_instruction.md")
    if proj.exists():
        return proj.read_text(encoding="utf-8")

    # Last resort: minimal prompt
    return "Return {\"results\": []} with same length as input items."


def prepare_item_payload(row: Row, content: Optional[str], max_chars: int = 8000) -> Dict[str, Any]:
    # Priority: 1) full_content from scraper, 2) fetched content, 3) snippet
    analyzable_content = None

    if hasattr(row, 'full_content') and row.full_content:
        analyzable_content = row.full_content
    elif content:  # fetched via trafilatura
        analyzable_content = content
    elif row.snippet:
        analyzable_content = row.snippet

    # Truncate if too long to control costs
    if analyzable_content and len(analyzable_content) > max_chars:
        analyzable_content = analyzable_content[:max_chars] + "...[truncated]"

    return {
        "title": row.title,
        "snippet": row.snippet[:280],  # Keep short preview
        "source": row.source or row.publication_info,
        "date": row.date,
        "url": row.link,
        "language": row.language,
        "content": analyzable_content,  # This is what GPT analyzes
    }


def fetch_content(url: str, timeout_s: int = 10) -> Optional[str]:
    if trafilatura is None:
        return None
    try:
        downloaded = trafilatura.fetch_url(url, timeout=timeout_s)
        if not downloaded:
            return None
        extracted = trafilatura.extract(downloaded, include_comments=False, favor_recall=True)
        if not extracted:
            return None
        # Cap to ~8000 chars to control token usage
        return extracted[:8000]
    except Exception:
        return None


def openai_client() -> OpenAI:
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment or .env")
    return OpenAI(api_key=key)


@retry(wait=wait_exponential_jitter(initial=1, max=20), stop=stop_after_attempt(4))
def call_llm(client: OpenAI, model: str, system_prompt: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    user_payload = json.dumps({"items": items}, ensure_ascii=False)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        max_tokens=4096,  # Increased from 1200 to handle larger batches
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except Exception as e:
        print(f"JSON parse error: {e}")
        print(f"LLM response (first 500 chars): {content[:500]}")
        print(f"System prompt (first 200 chars): {system_prompt[:200]}")
        # Fall back to non_intel for all items in batch
        return [
            {
                "label": "non_intel",
                "confidence": 0.0,
                "pmesii": [],
                "source_type": "other",
                "admiralty": {"source_reliability": "D", "info_credibility": 4},
                "rationale": "LLM parse error; defaulted to non_intel",
            }
            for _ in items
        ]
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        # Same fallback
        return [
            {
                "label": "non_intel",
                "confidence": 0.0,
                "pmesii": [],
                "source_type": "other",
                "admiralty": {"source_reliability": "D", "info_credibility": 4},
                "rationale": "LLM response not list; defaulted to non_intel",
            }
            for _ in items
        ]
    # Right-size to batch
    if len(results) < len(items):
        results.extend([
            {
                "label": "non_intel",
                "confidence": 0.0,
                "pmesii": [],
                "source_type": "other",
                "admiralty": {"source_reliability": "D", "info_credibility": 4},
                "rationale": "LLM shorter than batch; filled default",
            }
        ] * (len(items) - len(results)))
    elif len(results) > len(items):
        results = results[: len(items)]
    return results


def write_csv(path: pathlib.Path, fieldnames: List[str], rows: Iterable[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            filtered = {k: r.get(k) for k in fieldnames}
            w.writerow(filtered)


def ensure_dir(p: pathlib.Path):
    p.mkdir(parents=True, exist_ok=True)


def to_bibtex_key(title: Optional[str], url: Optional[str]) -> str:
    base = title or (url or "source")
    slug = slugify(base)[:40] or "source"
    year = dt.datetime.now().year
    return f"{slug}{year}"


def write_bibtex(path: pathlib.Path, rows: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            title = r.get("title") or "Untitled"
            url = r.get("link")
            year = None
            m = re.search(r"(20\d{2})", str(r.get("date") or ""))
            if m:
                year = m.group(1)
            org = r.get("source") or r.get("publication_info") or ""
            key = to_bibtex_key(title, url)
            f.write("@misc{" + key + ",\n")
            f.write(f"  title={{" + title.replace("{", "").replace("}", "") + "}},\n")
            if org:
                f.write(f"  howpublished={{" + org.replace("{", "").replace("}", "") + "}},\n")
            if year:
                f.write(f"  year={{" + year + "}},\n")
            if url:
                f.write(f"  url={{" + url + "}},\n")
            f.write("}\n\n")


def write_pmesii_md(path: pathlib.Path, rows: List[Dict[str, Any]]):
    buckets = {k: [] for k in ["Areas", "Structures", "Capabilities", "Organisations", "People", "Events"]}
    for r in rows:
        for tag in r.get("pmesii", []) or []:
            if tag in buckets:
                buckets[tag].append(r)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# PMESII Infrastructure Summary\n\n")
        for k in ["Areas", "Structures", "Capabilities", "Organisations", "People", "Events"]:
            items = buckets[k]
            f.write(f"## {k} ({len(items)})\n\n")
            for r in items[:3]:
                title = r.get("title") or "(no title)"
                url = r.get("link") or ""
                f.write(f"- {title} — {url}\n")
            f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze search results with LLM and export scores/PMESII/BibTeX")
    parser.add_argument("--results-dir", required=True, help="Timestamped results dir, e.g. search_results/20251015_001826")
    parser.add_argument("--input", default="results_deduped.csv", help="Input CSV (deduped or raw)")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model name")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0, help="Only analyze first N rows if >0")
    parser.add_argument("--no-fetch", action="store_true", help="Do not fetch article text")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache reuse")
    parser.add_argument("--max-content-chars", type=int, default=8000, help="Max content length for analysis (default 8000)")
    args = parser.parse_args()

    results_dir = pathlib.Path(args.results_dir)
    input_csv = results_dir / args.input
    ensure_dir(results_dir)

    # Ensure a deduped CSV exists if the requested input is missing
    if not input_csv.exists():
        try:
            dedup_target = results_dir / "results_deduped.csv"
            cmd = [
                sys.executable,
                "export_results_to_csv.py",
                "--results-dir", str(results_dir),
                "--output", "results_deduped.csv",
                "--dedupe",
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            if dedup_target.exists():
                input_csv = dedup_target
        except Exception:
            # If export fails, proceed and rely on in-memory dedupe below
            pass

    rows = load_rows(input_csv, limit=args.limit if args.limit and args.limit > 0 else None)
    # Safety net: de-duplicate rows in memory before analysis
    rows = dedupe_rows(rows)

    # cache
    cache_path = results_dir / "analysis_cache.jsonl"
    cache: Dict[str, Dict[str, Any]] = {}
    if cache_path.exists() and not args.no_cache:
        with open(cache_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("url"):
                        cache[rec["url"]] = rec
                except Exception:
                    continue

    system_prompt = load_system_prompt(results_dir)
    print(f"Loaded prompt (length: {len(system_prompt)} chars)")
    if len(system_prompt) < 100:
        print(f"WARNING: Prompt seems too short. Content: {system_prompt[:200]}")
    client = openai_client()

    enriched_rows: List[Dict[str, Any]] = []
    batch: List[Tuple[Row, Dict[str, Any]]] = []
    
    total_rows = len(rows)
    processed_count = 0

    def flush_batch():
        nonlocal batch, enriched_rows
        if not batch:
            return
        items_payload = [p for (_r, p) in batch]
        results = call_llm(client, args.model, system_prompt, items_payload)
        if len(results) != len(batch):
            # Attempt to realign by truncation; otherwise raise
            results = results[: len(batch)]
        for (row, payload), label in zip(batch, results):
            # Normalize fields defensively
            lab = label.get("label") if isinstance(label.get("label"), str) else "non_intel"
            lab = lab if lab in ("intel", "non_intel") else "non_intel"
            try:
                conf = float(label.get("confidence"))
            except Exception:
                conf = 0.0
            if conf < 0:
                conf = 0.0
            if conf > 1:
                conf = 1.0
            pmesii = [x for x in (label.get("pmesii") or []) if x in ["Areas","Structures","Capabilities","Organisations","People","Events"]]
            src_type = label.get("source_type") if isinstance(label.get("source_type"), str) else "other"
            if src_type not in ("news","report","journal","gov","NGO","company","think_tank","other"):
                src_type = "other"
            admiralty = label.get("admiralty") or {}
            src_rel = admiralty.get("source_reliability") if isinstance(admiralty.get("source_reliability"), str) else "D"
            if src_rel not in ("A","B","C","D","E","F"):
                src_rel = "D"
            try:
                info_cred = int(admiralty.get("info_credibility"))
            except Exception:
                info_cred = 4
            if info_cred not in (1,2,3,4,5,6):
                info_cred = 4
            rationale = label.get("rationale") or ""
            if len(rationale) > 280:
                rationale = rationale[:277] + "..."
            enriched = {
                **payload,
                "category": row.category,
                "query": row.query,
                "language": row.language,
                "engine": row.engine,
                "title": row.title,
                "link": row.link,
                "source": row.source,
                "publication_info": row.publication_info,
                "pdf_link": row.pdf_link,
                "date": row.date,
                "snippet": row.snippet,
                "position": row.position,
                "year_min": row.year_min,
                "year_max": row.year_max,
                "occurrences": row.occurrences,
                "label": lab,
                "confidence": conf,
                "pmesii": pmesii,
                "source_type": src_type,
                "admiralty_source_reliability": src_rel,
                "admiralty_info_credibility": info_cred,
                "rationale": rationale,
            }
            enriched_rows.append(enriched)
            # update cache
            if enriched.get("url"):
                cache[enriched["url"]] = enriched
        batch = []

    for row in tqdm(rows, desc="Analyzing"):
        url = normalize_url(row.link)
        cached = cache.get(url or "") if url else None
        if cached and not args.no_cache:
            # Use cached and continue
            enriched_rows.append(cached)
            processed_count += 1
            continue
        content = None
        if not args.no_fetch and url:
            content = fetch_content(url)
        payload = prepare_item_payload(row, content, args.max_content_chars)
        batch.append((row, payload))
        if len(batch) >= args.batch_size:
            flush_batch()
            processed_count += len(batch)
            print(f"Progress: {processed_count}/{total_rows} ({int(100*processed_count/total_rows)}%)")
            # Gentle pacing
            time.sleep(0.5)

    flush_batch()
    if batch:
        processed_count += len(batch)

    # Write cache
    with open(cache_path, "w", encoding="utf-8") as f:
        for rec in enriched_rows:
            f.write(json.dumps({k: rec.get(k) for k in rec.keys()}, ensure_ascii=False) + "\n")

    # CSV outputs
    base_fields = [
        "category","query","language","engine","title","link","source","publication_info","pdf_link","date","snippet","position","year_min","year_max","occurrences",
        "label","confidence","pmesii","source_type","admiralty_source_reliability","admiralty_info_credibility","rationale"
    ]
    all_csv = results_dir / "results_scored.csv"
    write_csv(all_csv, base_fields, enriched_rows)

    intel_rows = [r for r in enriched_rows if (r.get("label") == "intel")]
    non_rows = [r for r in enriched_rows if (r.get("label") == "non_intel")]
    write_csv(results_dir / "results_scored_intel.csv", base_fields, intel_rows)
    write_csv(results_dir / "results_scored_non_intel.csv", base_fields, non_rows)

    # PMESII markdown
    write_pmesii_md(results_dir / "pmesii_infrastructure.md", intel_rows)

    # BibTeX for intel-only
    write_bibtex(results_dir / "intel_sources.bib", intel_rows)

    print(f"Wrote: {all_csv}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


