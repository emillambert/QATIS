#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
import concurrent.futures as futures
import threading

import yaml
from dotenv import load_dotenv
from search_apis import load_scraperapi_key, scraperapi_google_search, openalex_search


def load_scraperapi_key_compat() -> str:
    """Load ScraperAPI key; wrapper for compatibility."""
    return load_scraperapi_key()


def read_queries(queries_path: str) -> Dict[str, List[str]]:
    with open(queries_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("queries.yaml must be a mapping of category -> list of queries")
    normalized: Dict[str, List[str]] = {}
    for category, queries in data.items():
        if not isinstance(queries, list):
            raise ValueError(f"Category '{category}' must map to a list of query strings")
        normalized[category] = [str(q).strip() for q in queries if str(q).strip()]
    return normalized


def sanitize_filename(value: str, max_length: int = 120) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    if len(safe) > max_length:
        safe = safe[: max_length - 8] + "__etc"
    return safe or "query"


def compose_google_tbs(year_min: int, year_max: int) -> str:
    # Custom date range: https://serpapi.com/google-tbs-parameters
    return f"cdr:1,cd_min:1/1/{year_min},cd_max:12/31/{year_max}"


def run_google_search(
    api_key: str,
    query: str,
    year_min: int,
    year_max: int,
    top_k: int,
    lang_region: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run Google search using ScraperAPI."""
    return scraperapi_google_search(
        api_key=api_key,
        query=query,
        year_min=year_min,
        year_max=year_max,
        top_k=top_k,
        lang_region=lang_region,
    )


def run_scholar_search(
    api_key: str,
    query: str,
    year_min: int,
    year_max: int,
    top_k: int,
    lang_region: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run academic search using OpenAlex API (free, unlimited)."""
    return openalex_search(
        query=query,
        year_min=year_min,
        year_max=year_max,
        top_k=top_k,
        lang_region=lang_region,
    )


def write_markdown(
    out_dir: pathlib.Path,
    category: str,
    query: str,
    year_min: int,
    year_max: int,
    results_by_engine: Dict[str, List[Dict[str, Any]]],
    lang_label: Optional[str],
) -> pathlib.Path:
    filename = sanitize_filename(f"{category}__{query}__{lang_label or 'en'}") + ".md"
    out_path = out_dir / filename
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Query: {query}\n")
        f.write(f"- Category: {category}\n")
        f.write(f"- Date range: {year_min}–{year_max}\n")
        if lang_label:
            f.write(f"- Language: {lang_label}\n")
        f.write("\n")
        for engine_name, items in results_by_engine.items():
            f.write(f"## {engine_name.capitalize()}\n\n")
            if not items:
                f.write("(no results)\n\n")
                continue
            for idx, item in enumerate(items, 1):
                title = item.get("title") or "(no title)"
                link = item.get("link") or ""
                snippet = item.get("snippet") or ""
                source = item.get("source") or item.get("publication_info") or ""
                date = item.get("date") or ""
                pdf_link = item.get("pdf_link") or ""
                f.write(f"{idx}. {title}\n")
                if source:
                    f.write(f"   - Source: {source}\n")
                if date:
                    f.write(f"   - Date: {date}\n")
                if link:
                    f.write(f"   - URL: {link}\n")
                if pdf_link:
                    f.write(f"   - PDF: {pdf_link}\n")
                if snippet:
                    f.write(f"   - Summary: {snippet}\n")
                f.write("\n")
    return out_path


def write_json(
    out_dir: pathlib.Path,
    category: str,
    query: str,
    year_min: int,
    year_max: int,
    results_by_engine: Dict[str, List[Dict[str, Any]]],
    lang_label: Optional[str],
) -> pathlib.Path:
    filename = sanitize_filename(f"{category}__{query}__{lang_label or 'en'}") + ".json"
    out_path = out_dir / filename
    payload = {
        "category": category,
        "query": query,
        "year_min": year_min,
        "year_max": year_max,
        "language": lang_label or "en",
        "results": results_by_engine,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Google and Scholar searches for predefined queries")
    parser.add_argument("--queries", default="queries.yaml", help="Path to queries.yaml")
    parser.add_argument("--output-dir", default="search_results", help="Directory to write results")
    parser.add_argument("--year-min", type=int, default=2024, help="Lower bound year filter")
    parser.add_argument("--year-max", type=int, default=2025, help="Upper bound year filter")
    parser.add_argument("--top-k", type=int, default=3, help="Top results per engine per query")
    parser.add_argument(
        "--engines",
        nargs="+",
        default=["web", "scholar"],
        choices=["web", "scholar"],
        help="Which engines to query",
    )
    parser.add_argument("--include-ru", action="store_true", help="Also run searches with Russian language bias (lr=lang_ru)")
    parser.add_argument("--include-ro", action="store_true", help="Also run searches with Romanian language bias (lr=lang_ro)")
    parser.add_argument("--concurrency", type=int, default=6, help="Number of concurrent query tasks")
    parser.add_argument("--no-markdown", action="store_true", help="Skip writing per-query markdown files for speed")
    args = parser.parse_args()

    api_key = load_scraperapi_key_compat()
    queries_by_category = read_queries(args.queries)

    output_root = pathlib.Path(args.output_dir)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = output_root / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    index_entries: List[Dict[str, Any]] = []

    lang_variants: List[Tuple[str, Optional[str]]] = [("en", None)]
    if args.include_ru:
        lang_variants.append(("ru", "lang_ru"))
    if args.include_ro:
        lang_variants.append(("ro", "lang_ro"))

    # Build task list
    tasks: List[Tuple[str, str, Tuple[str, Optional[str]]]] = []
    for category, queries in queries_by_category.items():
        for query in queries:
            for lang_label, lang_region in lang_variants:
                tasks.append((category, query, (lang_label, lang_region)))

    total_tasks = len(tasks)
    completed = 0
    completed_lock = threading.Lock()

    def process_task(task: Tuple[str, str, Tuple[str, Optional[str]]]) -> Dict[str, Any]:
        category, query, (lang_label, lang_region) = task
        results_by_engine: Dict[str, List[Dict[str, Any]]] = {}

        # Run engines concurrently per task for speed
        engine_results: Dict[str, List[Dict[str, Any]]] = {}

        def run_engine(name: str):
            if name == "web":
                return run_google_search(
                    api_key=api_key,
                    query=query,
                    year_min=args.year_min,
                    year_max=args.year_max,
                    top_k=args.top_k,
                    lang_region=None,
                )
            elif name == "scholar":
                return run_scholar_search(
                    api_key=api_key,
                    query=query,
                    year_min=args.year_min,
                    year_max=args.year_max,
                    top_k=args.top_k,
                    lang_region=lang_region,
                )
            return []

        inner_engines: List[str] = []
        # Only run web once for English (lang_region None)
        if "web" in args.engines and lang_region is None:
            inner_engines.append("web")
        if "scholar" in args.engines:
            inner_engines.append("scholar")

        if inner_engines:
            with futures.ThreadPoolExecutor(max_workers=len(inner_engines)) as inner_pool:
                futs = {inner_pool.submit(run_engine, en): en for en in inner_engines}
                for fut in futures.as_completed(futs):
                    en = futs[fut]
                    try:
                        engine_results[en] = fut.result() or []
                    except Exception:
                        engine_results[en] = []

        results_by_engine.update(engine_results)

        md_path = None
        if not args.no_markdown:
            md_path = write_markdown(
                out_dir=out_dir,
                category=category,
                query=query,
                year_min=args.year_min,
                year_max=args.year_max,
                results_by_engine=results_by_engine,
                lang_label=lang_label,
            )
        json_path = write_json(
            out_dir=out_dir,
            category=category,
            query=query,
            year_min=args.year_min,
            year_max=args.year_max,
            results_by_engine=results_by_engine,
            lang_label=lang_label,
        )
        return {
            "category": category,
            "query": query,
            "language": lang_label,
            "markdown": str(md_path) if md_path else "",
            "json": str(json_path),
        }

    if total_tasks:
        print(f"Progress: 0/{total_tasks} (0%) - Starting collection...")
        sys.stdout.flush()

    with futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        future_map = {pool.submit(process_task, t): t for t in tasks}
        for fut in futures.as_completed(future_map):
            try:
                entry = fut.result()
                index_entries.append(entry)
            except Exception:
                # Skip failed task, but continue
                pass
            with completed_lock:
                completed += 1
                pct = int(100 * completed / total_tasks) if total_tasks else 100
                print(f"Progress: {completed}/{total_tasks} ({pct}%) - Collected")
                sys.stdout.flush()

    index_path = out_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({"entries": index_entries}, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(index_entries)} query files under {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


