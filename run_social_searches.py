#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import pathlib
import os
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


def scrape_x_snscrape(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Scrape Twitter/X using snscrape (free). Often blocked by X."""
    items: List[Dict[str, Any]] = []
    try:
        import snscrape.modules.twitter as sntwitter
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
        print(f"snscrape unavailable or failed: {e}")
    return items


def scrape_x_twscrape(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Scrape Twitter/X using twscrape (requires logged-in session)."""
    items: List[Dict[str, Any]] = []
    try:
        from twscrape import API
        import asyncio
        import os as _os

        session_dir = _os.getenv("X_SESSION_DIR") or _os.path.expanduser("~/.twscrape")
        api = API(path=session_dir)

        async def run():
            try:
                await api.pool.login_all()
            except Exception:
                # proceed even if already logged in
                pass
            count = 0
            async for t in api.search(query):
                if count >= top_k:
                    break
                try:
                    content = (t.rawContent or "")
                    username = getattr(t.user, "username", None)
                    items.append(
                        {
                            "title": content[:120] or "(no title)",
                            "link": f"https://x.com/{username}/status/{t.id}" if username else None,
                            "source": username,
                            "date": t.date.isoformat() if getattr(t, "date", None) else None,
                            "snippet": content[:500],
                            "engine": "x",
                        }
                    )
                    count += 1
                except Exception:
                    continue

        asyncio.run(run())
    except Exception as e:
        print(f"twscrape failed: {e}")
    return items


def scrape_x_nitter(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Scrape Twitter/X via public Nitter mirrors (best-effort)."""
    items: List[Dict[str, Any]] = []
    try:
        import requests
        from bs4 import BeautifulSoup
        import urllib.parse

        nitter_hosts = [
            "https://nitter.net",
            "https://nitter.poast.org",
            "https://nitter.lacontrevoie.fr",
        ]
        for host in nitter_hosts:
            try:
                url = f"{host}/search?f=tweets&q={urllib.parse.quote_plus(query)}"
                r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                timeline_items = soup.select("div.timeline > div.timeline-item")
                for art in timeline_items[:top_k]:
                    try:
                        user_el = art.select_one("a.username")
                        user = user_el.get_text(strip=True) if user_el else None
                        content_el = art.select_one("div.tweet-content")
                        content = content_el.get_text(" ", strip=True) if content_el else ""
                        link_el = art.select_one("a[href*='/status/']")
                        nlink = link_el.get("href") if link_el else None
                        x_link = f"https://x.com{nlink}" if nlink else None
                        date_el = art.select_one("span.tweet-date > a")
                        date = date_el.get("title") if date_el else None
                        items.append(
                            {
                                "title": content[:120] or "(no title)",
                                "link": x_link,
                                "source": (user or "").lstrip("@") or None,
                                "date": date,
                                "snippet": content[:500],
                                "engine": "x",
                            }
                        )
                    except Exception:
                        continue
                if items:
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"Nitter scraping failed: {e}")
    return items


def scrape_x(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Best-effort X scraping: snscrape → twscrape → Nitter."""
    items = scrape_x_snscrape(query, top_k)
    if items:
        return items
    items = scrape_x_twscrape(query, top_k)
    if items:
        return items
    return scrape_x_nitter(query, top_k)


def scrape_youtube_enhanced(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Scrape YouTube with FULL transcripts/captions (crucial for GPT analysis)."""
    items: List[Dict[str, Any]] = []
    try:
        from yt_dlp import YoutubeDL
        import re
    except ImportError:
        return items

    try:
        # Extract video info
        with YoutubeDL({"quiet": True, "nocheckcertificate": True}) as ydl:
            info = ydl.extract_info(f"ytsearch{top_k}:{query}", download=False)

            for e in (info.get("entries") or []):
                video_id = e.get("id")
                transcript_text = ""
                transcript_available = False

                # Try to get transcript/captions
                if video_id:
                    try:
                        from youtube_transcript_api import YouTubeTranscriptApi
                        # Try multiple languages in priority order for Moldova
                        for lang_codes in [['en'], ['ro'], ['ru'], ['en', 'ro', 'ru']]:
                            try:
                                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_codes)
                                transcript_text = " ".join([seg['text'] for seg in transcript])
                                transcript_available = True
                                break
                            except:
                                continue
                    except Exception as e:
                        print(f"No transcript for {video_id}: {e}")

                # Fallback hierarchy: transcript > description
                if transcript_available:
                    full_content = f"{e.get('description') or ''}\n\n[TRANSCRIPT]\n{transcript_text}"
                    content_quality = "high"  # Has transcript
                else:
                    full_content = e.get("description") or ""
                    content_quality = "low"   # Description only

                # Clean up transcript text
                if transcript_text:
                    transcript_text = re.sub(r'\s+', ' ', transcript_text).strip()

                items.append({
                    "title": e.get("title"),
                    "link": e.get("webpage_url"),
                    "source": e.get("uploader") or e.get("channel"),
                    "date": e.get("upload_date"),
                    "snippet": full_content[:500],  # Preview
                    "full_content": full_content[:8000],  # Full text for GPT (matching trafilatura limit)
                    "engine": "youtube",
                    "duration": e.get("duration"),
                    "view_count": e.get("view_count"),
                    "content_quality": content_quality,
                })
    except Exception as e:
        print(f"YouTube scraping failed: {e}")

    return items


def scrape_youtube(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Scrape YouTube using yt-dlp (legacy, fallback)."""
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


def scrape_reddit_enhanced(query: str, top_k: int, subreddits: List[str] = None) -> List[Dict[str, Any]]:
    """Scrape Reddit with top comments (crucial for context)."""
    items = []
    try:
        import praw
        import os

        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent="QATIS OSINT v1.0"
        )

        search_target = "+".join(subreddits) if subreddits else "all"
        subreddit = reddit.subreddit(search_target)

        for submission in subreddit.search(query, limit=top_k, sort='relevance'):
            # Get top comments for context
            submission.comments.replace_more(limit=0)  # Remove "load more" placeholders
            top_comments = []
            for comment in submission.comments.list()[:10]:  # Top 10 comments
                if hasattr(comment, 'body') and len(comment.body) > 20:
                    top_comments.append(f"[{comment.score}↑] {comment.body[:500]}")

            # Combine post + comments
            full_content = f"{submission.selftext}\n\n[TOP COMMENTS]\n" + "\n\n".join(top_comments)

            items.append({
                "title": submission.title,
                "link": f"https://reddit.com{submission.permalink}",
                "source": f"r/{submission.subreddit.display_name}",
                "date": dt.datetime.fromtimestamp(submission.created_utc).isoformat(),
                "snippet": submission.selftext[:500] if submission.selftext else "",
                "full_content": full_content[:8000],  # For GPT analysis
                "engine": "reddit",
                "score": submission.score,
                "num_comments": submission.num_comments,
            })
    except Exception as e:
        print(f"Reddit scraping failed: {e}")
    return items


def scrape_vk_enhanced(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Scrape VK (VKontakte) - crucial for Moldova/Eastern Europe."""
    items = []
    try:
        import vk_api
        import os as _os

        token = _os.getenv("VK_TOKEN")
        if not token:
            print("VK scraping requires VK_TOKEN (user access token with newsfeed scope).")
            return items

        vk_session = vk_api.VkApi(token=token)
        api = vk_session.get_api()

        results = api.newsfeed.search(q=query, count=min(top_k, 200))

        for item in results.get('items', [])[:top_k]:
            full_text = item.get('text', '')

            # Include attachment info (photos, videos, links)
            attachments_info = []
            for att in item.get('attachments', []):
                att_type = att.get('type')
                if att_type == 'photo':
                    attachments_info.append(f"[PHOTO: {att.get('photo', {}).get('text', 'no description')}]")
                elif att_type == 'video':
                    attachments_info.append(f"[VIDEO: {att.get('video', {}).get('title', 'no title')}]")
                elif att_type == 'link':
                    link_data = att.get('link', {})
                    attachments_info.append(f"[LINK: {link_data.get('title')} - {link_data.get('description', '')}]")

            full_content = f"{full_text}\n\n{' '.join(attachments_info)}"

            items.append({
                "title": full_text[:120] if full_text else "(no text)",
                "link": f"https://vk.com/wall{item.get('owner_id')}_{item.get('id')}",
                "source": f"VK user {item.get('owner_id')}",
                "date": dt.datetime.fromtimestamp(item.get('date', 0)).isoformat(),
                "snippet": full_text[:500],
                "full_content": full_content[:8000],
                "engine": "vk",
                "likes": item.get('likes', {}).get('count', 0),
            })
    except Exception as e:
        print(f"VK scraping failed: {e}")
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
    parser = argparse.ArgumentParser(description="Run enhanced social media searches (X, YouTube, Reddit, VK, Telegram)")
    parser.add_argument("--queries", default="queries_social.yaml", help="Path to queries_social.yaml")
    parser.add_argument("--output-dir", default="search_results_social", help="Directory to write results")
    parser.add_argument("--year-min", type=int, default=2024, help="Lower bound year filter (used inside query strings)")
    parser.add_argument("--year-max", type=int, default=2025, help="Upper bound year filter (used inside query strings)")
    parser.add_argument("--top-k", type=int, default=20, help="Top results per platform per query")
    parser.add_argument("--platforms", nargs="+", default=["x", "youtube"], choices=["x", "youtube", "reddit", "vk", "telegram"], help="Which platforms to scrape")
    parser.add_argument("--telegram", action="store_true", help="Enable Telegram scraping (requires credentials)")
    parser.add_argument("--tele-api-id", type=int, help="Telegram api_id")
    parser.add_argument("--tele-api-hash", type=str, help="Telegram api_hash")
    parser.add_argument("--use-transcripts", action="store_true", default=True, help="Use YouTube transcripts (default: on)")
    parser.add_argument("--no-transcripts", action="store_true", help="Disable YouTube transcripts")
    parser.add_argument("--include-comments", action="store_true", default=True, help="Include Reddit top comments (default: on)")
    parser.add_argument("--no-comments", action="store_true", help="Disable Reddit comments")
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
            # Use enhanced scraper if transcripts are enabled and available
            if args.use_transcripts and not args.no_transcripts:
                try:
                    items = scrape_youtube_enhanced(query=query, top_k=args.top_k)
                except ImportError:
                    print("⚠️ youtube-transcript-api not available, falling back to basic scraper")
                    items = scrape_youtube(query=query, top_k=args.top_k)
            else:
                items = scrape_youtube(query=query, top_k=args.top_k)

            md_path = write_markdown(out_dir, "youtube", query, args.year_min, args.year_max, items, "en")
            json_path = write_json(out_dir, "youtube", query, args.year_min, args.year_max, items, "en")
            index_entries.append({"category": "youtube", "query": query, "language": "en", "markdown": str(md_path), "json": str(json_path)})

    # Reddit
    if "reddit" in args.platforms and isinstance(queries_cfg.get("reddit"), dict):
        r_section = queries_cfg["reddit"]
        r_queries: List[str] = [str(q).strip() for q in (r_section.get("queries") or []) if str(q).strip()]
        r_subreddits = [str(s).strip() for s in (r_section.get("subreddits") or []) if str(s).strip()]
        for query in r_queries:
            # Use enhanced scraper if comments are enabled and available
            if args.include_comments and not args.no_comments:
                try:
                    items = scrape_reddit_enhanced(query=query, top_k=args.top_k, subreddits=r_subreddits or None)
                except ImportError:
                    print("⚠️ praw not available, falling back to basic Reddit scraper")
                    # For now, fall back to no results since we don't have a basic Reddit scraper
                    items = []
            else:
                # Basic Reddit scraper would go here if implemented
                items = []

            if items:  # Only write if we got results
                md_path = write_markdown(out_dir, "reddit", query, args.year_min, args.year_max, items, "en")
                json_path = write_json(out_dir, "reddit", query, args.year_min, args.year_max, items, "en")
                index_entries.append({"category": "reddit", "query": query, "language": "en", "markdown": str(md_path), "json": str(json_path)})

    # VK
    if "vk" in args.platforms and isinstance(queries_cfg.get("vk"), dict):
        v_section = queries_cfg["vk"]
        v_queries: List[str] = [str(q).strip() for q in (v_section.get("queries") or []) if str(q).strip()]
        for query in v_queries:
            items = scrape_vk_enhanced(query=query, top_k=args.top_k)
            if items:  # Only write if we got results
                md_path = write_markdown(out_dir, "vk", query, args.year_min, args.year_max, items, "en")
                json_path = write_json(out_dir, "vk", query, args.year_min, args.year_max, items, "en")
                index_entries.append({"category": "vk", "query": query, "language": "en", "markdown": str(md_path), "json": str(json_path)})

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


