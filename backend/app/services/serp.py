import re
from typing import Protocol

from app.models import SERPResult


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


def get_serp_client(use_mock: bool = True) -> SERPClient:
    if use_mock:
        return MockSERPClient()
    raise NotImplementedError("Real SERP client not implemented yet")
