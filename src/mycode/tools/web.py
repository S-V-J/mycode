"""Web access tools for the MyCode Agent."""

import httpx
from ddgs import DDGS
from markdownify import markdownify as md
from rich.console import Console

console = Console()


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return formatted results.

    Args:
        query: The search query
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Formatted search results as markdown
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"No results found for query: {query}"

        output = f"## Web Search Results for: {query}\n\n"
        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            href = result.get('href', '')
            body = result.get('body', 'No description')
            output += f"### {i}. [{title}]({href})\n{body}\n\n"

        return output
    except Exception as e:
        return f"Error performing web search: {str(e)}"


def fetch_url(url: str) -> str:
    """
    Fetch a URL and convert its content to markdown.

    Args:
        url: The URL to fetch

    Returns:
        Page content as markdown
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

            # Convert HTML to markdown
            content = md(response.text, heading_style="ATX")

            # Truncate if too long
            if len(content) > 15000:
                content = content[:15000] + "\n\n... [Content truncated - too long]"

            return f"## Fetched from: {url}\n\n{content}"
    except httpx.TimeoutException:
        return f"Error: Request timed out while fetching {url}"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} while fetching {url}"
    except Exception as e:
        return f"Error fetching URL: {str(e)}"