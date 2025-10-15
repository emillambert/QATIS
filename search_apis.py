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
    
    Args:
        query: Search query
        year_min: Start year (note: DDG doesn't support date filtering via URL)
        year_max: End year
        top_k: Number of results
        lang_region: Language region (ignored for DDG)
    
    Returns:
        List of search result dicts
    """
    try:
        import urllib.parse
        import requests
        from bs4 import BeautifulSoup
        import time
        
        # Add year to query if specified
        search_query = f"{query} {year_min}..{year_max}" if year_min else query
        
        # Construct DuckDuckGo search URL
        params = {
            "q": search_query,
            "kl": "us-en",  # Region
        }
        
        ddg_url = f"https://html.duckduckgo.com/html/?{urllib.parse.urlencode(params)}"
        
        # Make request with headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Small delay to be respectful
        time.sleep(1)
        
        response = requests.get(ddg_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Parse results using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = []
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
                    # Extract actual URL from DDG redirect
                    import re
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
            except Exception as e:
                continue
        
        return items
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

