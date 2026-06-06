"""Search Web tool - Perform web searches and scrape content."""

import json
import urllib.request
import urllib.parse
import urllib.error
import re

TOOL_NAME = "search_web"
TOOL_DESCRIPTION = "Search the web for information and return top results"
TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query string"
        },
        "num_results": {
            "type": "integer",
            "description": "Number of results to return (max 10)",
            "default": 5
        }
    },
    "required": ["query"]
}

# Simple DuckDuckGo-style search fallback
SEARCH_ENGINES = [
    "https://www.google.com/search?q={q}",
    "https://duckduckgo.com/html/?q={q}",
]


def register(registry):
    """Register this tool with the registry."""
    registry.register(TOOL_NAME, handle, TOOL_DESCRIPTION, TOOL_PARAMETERS)


def handle(query: str, num_results: int = 5) -> dict:
    """Perform a web search and return results."""
    from urllib.request import Request, urlopen
    from urllib.parse import quote

    encoded = quote(query)
    results = []

    # Try DuckDuckGo lite (no JS required)
    try:
        ddg_url = f"https://lite.duckduckgo.com/lite/?q={encoded}"
        req = Request(ddg_url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        with urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            # Extract result links from DDG lite
            links = re.findall(
                r'<a[^>]*href="(https?://[^"]+)"[^>]*rel="nofollow"[^>]*>(.*?)</a>',
                html
            )
            for url, title in links[:num_results]:
                results.append({
                    "title": re.sub(r'<[^>]+>', '', title).strip(),
                    "url": url
                })
    except Exception:
        pass

    # If DuckDuckGo fails, return search URL for manual browsing
    if not results:
        results.append({
            "title": f"Search: {query}",
            "url": f"https://www.google.com/search?q={encoded}"
        })

    return {
        "success": len(results) > 0,
        "query": query,
        "results": results[:num_results],
        "result_count": len(results[:num_results]),
    }
