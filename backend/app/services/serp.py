import re
from typing import Any, Protocol

import httpx

from app.models import SERPResult

SERPAPI_BASE = "https://serpapi.com"
SERPAPI_TIMEOUT = 30.0


class SERPClient(Protocol):
    def get_serp(self, query: str) -> list[SERPResult]: ...


def _slug(query: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", query.lower().strip())
    return s.strip("-") or "topic"


# Predefined snippet fragments for variety (deterministic by index)
_SNIPPETS = [
    "Discover the best options and how they compare.",
    "Learn what experts recommend and why it matters.",
    "A complete guide to help you choose the right one.",
    "Find out which options rank highest in user reviews.",
    "Compare features, pricing, and pros and cons.",
    "Everything you need to know before you decide.",
    "Top picks based on real-world testing and feedback.",
    "See how leading solutions stack up side by side.",
    "Practical tips to get the most out of your choice.",
    "Updated for this year with the latest recommendations.",
]


class MockSERPClient:
    def get_serp(self, query: str) -> list[SERPResult]:
        slug = _slug(query)
        results = []
        title_templates = [
            f"Top 10 {query} in 2025: Best Picks",
            f"Best {query} Compared | Expert Review",
            f"{query}: Ultimate Buying Guide",
            f"{query} | Complete Guide and Reviews",
            f"Best {query} for Every Need",
            f"{query} Comparison: Which One to Choose",
            f"The Best {query} This Year",
            f"{query} Guide: Features and Pricing",
            f"Top-Rated {query} | 2025 Roundup",
            f"{query} | Tips and Recommendations",
        ]
        for i in range(1, 11):
            title = (title_templates[i - 1])[:70]
            snippet = f"Explore {query}. {_SNIPPETS[i - 1]}"
            results.append(
                SERPResult(
                    rank=i,
                    url=f"https://example.com/{slug}-{i}",
                    title=title[:70],
                    snippet=snippet[:160],
                )
            )
        return results


class SerpAPIClient:
    """SerpAPI client for Google search. Maps organic_results to SERPResult."""

    def __init__(self, api_key: str, base_url: str = SERPAPI_BASE, timeout: float = SERPAPI_TIMEOUT):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_serp(self, query: str) -> list[SERPResult]:
        url = f"{self.base_url}/search.json"
        params = {"q": query, "api_key": self.api_key}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
        data: dict[str, Any] = response.json()
        organic = data.get("organic_results") or []
        results = []
        for item in organic:
            if not isinstance(item, dict):
                continue
            position = item.get("position")
            title = item.get("title") or ""
            link = item.get("link") or ""
            snippet = item.get("snippet") or ""
            if position is not None:
                results.append(
                    SERPResult(
                        rank=int(position),
                        url=link[:2048],
                        title=title[:1024],
                        snippet=snippet[:2048],
                    )
                )
        results.sort(key=lambda r: r.rank)
        return results


def get_serp_client(use_mock: bool = True, settings=None) -> SERPClient:
    if use_mock:
        return MockSERPClient()
    if settings is None:
        from app.config import Settings
        settings = Settings()
    provider = getattr(settings, "serp_provider", "serpapi").lower()
    if provider == "serpapi":
        key = getattr(settings, "serpapi_key", None)
        if not (key and str(key).strip()):
            raise ValueError(
                "Real SERP requested but SERPAPI_KEY is not set. "
                "Set SERPAPI_KEY in the environment or use SERP_USE_MOCK=true."
            )
        return SerpAPIClient(api_key=str(key).strip())
    raise ValueError(
        f"Unknown SERP provider: {provider}. Set SERP_PROVIDER=serpapi or use SERP_USE_MOCK=true."
    )
