"""RSS fetching and feed item extraction for Morning Brief."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
import html
import logging
import re
from typing import Any

import feedparser
import httpx

from homeassistant.util import dt as dt_util

from .const import (
    CONF_TOPIC_FEEDS,
    CONF_TOPIC_NAME,
    FEED_ITEM_WORD_LIMIT,
    MAX_ITEMS_PER_FEED,
)

_LOGGER = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


class RSSFetcher:
    """Fetch and normalize RSS/Atom items."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        """Initialize the fetcher."""
        self._client = client

    async def async_fetch_topics(
        self, topics: list[dict[str, Any]], lookback_days: int
    ) -> list[dict[str, Any]]:
        """Fetch qualifying feed items for every configured topic."""
        cutoff = dt_util.utcnow().astimezone(timezone.utc) - timedelta(days=lookback_days)
        results: list[dict[str, Any]] = []

        for topic in topics:
            topic_name = topic[CONF_TOPIC_NAME]
            topic_items: list[dict[str, Any]] = []

            for feed_url in topic[CONF_TOPIC_FEEDS]:
                items = await self._async_fetch_feed_items(feed_url, cutoff)
                topic_items.extend(items)

            if not topic_items:
                _LOGGER.warning("Skipping topic '%s' because no feed items were available", topic_name)
                continue

            topic_items.sort(
                key=lambda item: item.get("published") or "",
                reverse=True,
            )
            results.append(
                {
                    "name": topic_name,
                    "topic_prompt": topic["topic_prompt"],
                    "items": topic_items,
                }
            )

        return results

    async def _async_fetch_feed_items(
        self, feed_url: str, cutoff: datetime
    ) -> list[dict[str, Any]]:
        """Fetch one feed and return the filtered item list."""
        try:
            response = await self._client.get(feed_url)
            response.raise_for_status()
        except httpx.HTTPError as err:
            _LOGGER.warning("Failed to fetch RSS feed %s: %s", feed_url, err)
            return []

        parsed = feedparser.parse(response.text)
        if getattr(parsed, "bozo", False):
            _LOGGER.warning("Feed %s is malformed and may be incomplete", feed_url)

        entries: list[dict[str, Any]] = []

        for entry in parsed.entries:
            published_at = self._parse_entry_datetime(entry)
            if published_at is None or published_at < cutoff:
                continue

            entries.append(
                {
                    "feed_url": feed_url,
                    "title": self._clean_text(entry.get("title", "Untitled item")),
                    "snippet": self._extract_snippet(entry),
                    "published": published_at.isoformat(),
                }
            )

        entries.sort(key=lambda item: item["published"], reverse=True)
        return entries[:MAX_ITEMS_PER_FEED]

    def _parse_entry_datetime(self, entry: Any) -> datetime | None:
        """Parse an entry timestamp into UTC."""
        for key in ("published_parsed", "updated_parsed", "created_parsed"):
            parsed = entry.get(key)
            if parsed is None:
                continue

            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)

        return None

    def _extract_snippet(self, entry: Any) -> str:
        """Extract the first 100 words from the item content."""
        raw = ""

        content = entry.get("content")
        if content and isinstance(content, list):
            raw = content[0].get("value", "")

        if not raw:
            raw = entry.get("summary", "") or entry.get("description", "")

        cleaned = self._clean_text(raw)
        words = cleaned.split()
        return " ".join(words[:FEED_ITEM_WORD_LIMIT])

    def _clean_text(self, value: str) -> str:
        """Strip HTML and normalize whitespace."""
        value = html.unescape(value or "")
        value = _TAG_RE.sub(" ", value)
        value = _SPACE_RE.sub(" ", value)
        return value.strip()

