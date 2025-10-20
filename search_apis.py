#!/usr/bin/env python3
"""
Unified search API client using ScraperAPI (web) + OpenAlex (academic) + social scrapers.
"""

import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv


def load_scraperapi_key() -> str:
    """Load SerpAPI key from environment."""
    load_dotenv()
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing SERPAPI_API_KEY. Set it in .env or your environment.")
    return api_key


def duckduckgo_search(
    query: str,
    year_min: int,
    year_max: int,
    top_k: int,
    lang_region: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run DuckDuckGo search using direct requests + BeautifulSoup (free, no API key).

    - Respects language via DDG 'kl' param (en/ru/ro).
    - Avoids adding year range if already present in the query.
    - Throttles to ~0.2–0.3 QPS with exponential backoff on 403/429.
    """
    try:
        import urllib.parse
        import requests
        from bs4 import BeautifulSoup
        import time
        import random
        import re

        # Map language bias to DDG 'kl' parameter
        kl_map = {
            None: "us-en",
            "lang_ru": "ru-ru",
            "lang_ro": "ro-ro",
        }
        kl = kl_map.get(lang_region, "us-en")

        # Avoid duplicate year range if already in query (e.g., "... 2024..2025")
        has_range = bool(re.search(r"\b20\d{2}\.\.20\d{2}\b", query))
        search_query = query if has_range else f"{query} {year_min}..{year_max}"

        # Rotate user agents to avoid detection
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        
        # Make request with enhanced headers to look more like a real browser
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9" if kl == "us-en" else ("ru-RU,ru;q=0.9" if kl == "ru-ru" else "ro-RO,ro;q=0.9"),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Referer": "https://duckduckgo.com/",
        }

        # Aggressive throttle with more randomness to appear human
        time.sleep(random.uniform(6.0, 10.0))

        # Retry with exponential backoff + jitter for 403/429/network errors
        last_exc = None
        for attempt in range(5):
            try:
                # Use session with persistent cookies
                session = requests.Session()
                
                # STEP 1: First visit DDG homepage to get cookies
                session.get("https://duckduckgo.com/", headers=headers, timeout=10)
                time.sleep(random.uniform(1.0, 2.0))
                
                # STEP 2: Now do the search via POST (more like real browser)
                ddg_url = "https://html.duckduckgo.com/html/"
                form_data = {
                    "q": search_query,
                    "kl": kl,
                    "df": "",  # date filter empty
                }
                
                # Update headers for POST
                post_headers = dict(headers)
                post_headers.update({
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://duckduckgo.com",
                })
                
                response = session.post(ddg_url, data=form_data, headers=post_headers, timeout=15, allow_redirects=True)
                if response.status_code in (403, 429):
                    raise RuntimeError(f"DDG blocked: {response.status_code}")
                response.raise_for_status()

                # Parse results using BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                items: List[Dict[str, Any]] = []
                # DuckDuckGo results are in divs with class 'result' or 'web-result'
                result_divs = soup.select('div.result, div.web-result, div.results_links')

                for idx, result_div in enumerate(result_divs[:top_k]):
                    try:
                        # Title and link
                        link_elem = result_div.select_one('a.result__a, a[class*="result"]')
                        snippet_elem = result_div.select_one('a.result__snippet, div.result__snippet, span.result__snippet')

                        if not link_elem:
                            continue

                        title = link_elem.get_text(strip=True)
                        link = link_elem.get('href', '')

                        # Clean DDG redirect URL
                        if link.startswith('/'):
                            match = re.search(r'uddg=([^&]+)', link)
                            if match:
                                link = urllib.parse.unquote(match.group(1))

                        items.append({
                            "title": title,
                            "link": link,
                            "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                            "source": "",
                            "date": "",
                            "position": idx + 1,
                            "engine": "duckduckgo"
                        })
                    except Exception:
                        continue

                return items
            except Exception as e:
                last_exc = e
                # Exponential backoff with jitter
                time.sleep((2 ** attempt) + random.uniform(0.2, 0.8))
                continue

        print(f"Error with DuckDuckGo search: {last_exc}")
        return []
    except Exception as e:
        print(f"Error with DuckDuckGo search: {e}")
        return []


def scraperapi_google_search(
    api_key: str,
    query: str,
    year_min: int,
    year_max: int,
    top_k: int,
    lang_region: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run web search using DuckDuckGo (free, no API key)."""
    return duckduckgo_search(query, year_min, year_max, top_k, lang_region)


def openalex_search(
    query: str,
    year_min: int,
    year_max: int,
    top_k: int,
    lang_region: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search academic papers using OpenAlex API (free, unlimited).
    
    Args:
        query: Search query
        year_min: Start year
        year_max: End year
        top_k: Number of results
        lang_region: Ignored (OpenAlex doesn't filter by language)
    
    Returns:
        List of academic paper dicts
    """
    try:
        from pyalex import Works
        import pyalex
        
        # Set user agent (required by OpenAlex)
        pyalex.config.email = "research@qatis.org"
        
        # Search with filters
        results = (
            Works()
            .search(query)
            .filter(publication_year=f"{year_min}-{year_max}")
            .get(per_page=min(top_k, 50))
        )
        
        items = []
        for idx, work in enumerate(results[:top_k]):
            # Extract PDF link if available
            pdf_link = None
            if work.get('primary_location'):
                pdf_link = work['primary_location'].get('pdf_url')
            if not pdf_link and work.get('best_oa_location'):
                pdf_link = work['best_oa_location'].get('pdf_url')
            
            # Publication info
            pub_info = ""
            if work.get('primary_location') and work['primary_location'].get('source'):
                pub_info = work['primary_location']['source'].get('display_name', '')
            
            # Year
            pub_year = work.get('publication_year', '')
            
            items.append({
                "title": work.get('title', ''),
                "link": work.get('id', ''),  # OpenAlex ID or DOI
                "snippet": (work.get('abstract') or '')[:500],
                "publication_info": f"{pub_info} ({pub_year})" if pub_info else str(pub_year),
                "pdf_link": pdf_link,
                "engine": "openalex"
            })
        
        return items
    except Exception as e:
        print(f"Error using OpenAlex for academic search: {e}")
        return []

