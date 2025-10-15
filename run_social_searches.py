#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import pathlib
from typing import Any, Dict, List, Optional, Tuple

import yaml


def sanitize_filename(value: str, max_length: int = 120) -> str:
    import re
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    if len(safe) > max_length:
        safe = safe[: max_length - 8] + "__etc"
    return safe or "query"


def read_social_queries(queries_path: str) -> Dict[str, Any]:
    with open(queries_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("queries_social.yaml must be a mapping: platform -> config")
    return data


def write_markdown(
    out_dir: pathlib.Path,
    category: str,
    query: str,
    year_min: int,
    year_max: int,
    results: List[Dict[str, Any]],
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
        f.write(f"## {category.capitalize()}\n\n")
        if not results:
            f.write("(no results)\n\n")
        for idx, item in enumerate(results, 1):
            title = item.get("title") or "(no title)"
            link = item.get("link") or ""
            snippet = item.get("snippet") or ""
            source = item.get("source") or ""
            date = item.get("date") or ""
            f.write(f"{idx}. {title}\n")
            if source:
                f.write(f"   - Source: {source}\n")
            if date:
                f.write(f"   - Date: {date}\n")
            if link:
                f.write(f"   - URL: {link}\n")
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
    results: List[Dict[str, Any]],
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
        "results": {category: results},
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def scrape_x(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Scrape Twitter/X using snscrape (free).
    
    Note: Twitter often blocks snscrape. If this fails, results will be empty.
    """
    items: List[Dict[str, Any]] = []
    try:
        import snscrape.modules.twitter as sntwitter
    except Exception as e:
        print(f"Could not import snscrape: {e}")
        return items
    
    try:
        for i, t in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            if i >= top_k:
                break
            try:
                username = getattr(t.user, "username", None)
                tweet_id = getattr(t, "id", None)
                content = getattr(t, "content", None) or ""
                date = getattr(t, "date", None)
                link = f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else None
                items.append(
                    {
                        "title": content[:120] or "(no title)",
                        "link": link,
                        "source": username,
                        "date": date.isoformat() if date else None,
                        "snippet": content,
                        "engine": "x",
                    }
                )
            except Exception:
                continue
    except Exception as e:
        print(f"Twitter scraping blocked or failed: {e}")
        print("Note: Twitter/X often blocks automated scraping. Consider using YouTube only.")
    
    return items


def scrape_youtube(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Scrape YouTube using yt-dlp (free)."""
    items: List[Dict[str, Any]] = []
    try:
        from yt_dlp import YoutubeDL
    except Exception:
        return items
    try:
        with YoutubeDL({"quiet": True, "nocheckcertificate": True}) as ydl:
            info = ydl.extract_info(f"ytsearch{top_k}:{query}", download=False)
            for e in (info.get("entries") or []):
                items.append(
                    {
                        "title": e.get("title"),
                        "link": e.get("webpage_url"),
                        "source": e.get("uploader") or e.get("channel"),
                        "date": e.get("upload_date"),
                        "snippet": (e.get("description") or "")[:280],
                        "engine": "youtube",
                    }
                )
    except Exception:
        pass
    return items


def scrape_telegram(channels: List[str], keywords: List[str], top_k: int) -> List[Dict[str, Any]]:
    """Scrape Telegram (requires Telethon setup; placeholder)."""
    # Placeholder - requires Telegram API credentials and session setup
    items: List[Dict[str, Any]] = []
    try:
        from telethon import TelegramClient
    except Exception:
        return items
    # We don't start a session here; this function is called with an active client in main
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Run social media searches (X and YouTube; optional Telegram)")
    parser.add_argument("--queries", default="queries_social.yaml", help="Path to queries_social.yaml")
    parser.add_argument("--output-dir", default="search_results_social", help="Directory to write results")
    parser.add_argument("--year-min", type=int, default=2024, help="Lower bound year filter (used inside query strings)")
    parser.add_argument("--year-max", type=int, default=2025, help="Upper bound year filter (used inside query strings)")
    parser.add_argument("--top-k", type=int, default=20, help="Top results per platform per query")
    parser.add_argument("--platforms", nargs="+", default=["x", "youtube"], choices=["x", "youtube", "telegram"], help="Which platforms to scrape")
    parser.add_argument("--telegram", action="store_true", help="Enable Telegram scraping (requires credentials)")
    parser.add_argument("--tele-api-id", type=int, help="Telegram api_id")
    parser.add_argument("--tele-api-hash", type=str, help="Telegram api_hash")
    args = parser.parse_args()

    queries_cfg = read_social_queries(args.queries)

    output_root = pathlib.Path(args.output_dir)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = output_root / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    index_entries: List[Dict[str, Any]] = []

    # X / Twitter
    if "x" in args.platforms and isinstance(queries_cfg.get("x"), dict):
        x_section = queries_cfg["x"]
        x_queries: List[str] = [str(q).strip() for q in (x_section.get("queries") or []) if str(q).strip()]
        for query in x_queries:
            items = scrape_x(query=query, top_k=args.top_k)
            md_path = write_markdown(out_dir, "x", query, args.year_min, args.year_max, items, "en")
            json_path = write_json(out_dir, "x", query, args.year_min, args.year_max, items, "en")
            index_entries.append({"category": "x", "query": query, "language": "en", "markdown": str(md_path), "json": str(json_path)})

    # YouTube
    if "youtube" in args.platforms and isinstance(queries_cfg.get("youtube"), dict):
        y_section = queries_cfg["youtube"]
        y_queries: List[str] = [str(q).strip() for q in (y_section.get("queries") or []) if str(q).strip()]
        for query in y_queries:
            items = scrape_youtube(query=query, top_k=args.top_k)
            md_path = write_markdown(out_dir, "youtube", query, args.year_min, args.year_max, items, "en")
            json_path = write_json(out_dir, "youtube", query, args.year_min, args.year_max, items, "en")
            index_entries.append({"category": "youtube", "query": query, "language": "en", "markdown": str(md_path), "json": str(json_path)})

    # Telegram (placeholder; only runs if explicitly enabled and creds present)
    if "telegram" in args.platforms and args.telegram and isinstance(queries_cfg.get("telegram"), dict):
        t_section = queries_cfg["telegram"]
        channels = [str(c).strip() for c in (t_section.get("channels") or []) if str(c).strip()]
        keywords = [str(k).strip() for k in (t_section.get("keywords") or []) if str(k).strip()]
        if args.tele_api_id and args.tele_api_hash and channels:
            # Intentionally leaving out actual scraping here; ensure credentials before implementing network calls
            items: List[Dict[str, Any]] = []
            md_path = write_markdown(out_dir, "telegram", ", ".join(channels[:3]), args.year_min, args.year_max, items, "en")
            json_path = write_json(out_dir, "telegram", ", ".join(channels[:3]), args.year_min, args.year_max, items, "en")
            index_entries.append({"category": "telegram", "query": ", ".join(channels[:3]), "language": "en", "markdown": str(md_path), "json": str(json_path)})

    index_path = out_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({"entries": index_entries}, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(index_entries)} query files under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


