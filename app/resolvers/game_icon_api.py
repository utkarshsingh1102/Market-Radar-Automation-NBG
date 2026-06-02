"""
Game Icon API resolver.

Calls an external service that returns the App Store / Play Store icon for a
given game name. Documented at fetch-inspiration-icon-strategy companion doc.

Endpoint:
    GET {base_url}/api/game/<url-encoded name>/icon.png   →  image bytes (200)
                                                          →  404 if not found

Configured via settings.game_icon_api_url (env: GAME_ICON_API_URL).
Cache key: cache/icons/api_<sha256(name.lower())>.png
"""
from __future__ import annotations

import hashlib
import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class GameIconApiResolver:
    def __init__(self, store, base_url: str, timeout: float = 15.0) -> None:
        self._store = store
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _cache_key(self, name: str) -> str:
        digest = hashlib.sha256(name.lower().encode()).hexdigest()
        return f"cache/icons/api_{digest}.png"

    async def resolve(self, name: str) -> bytes | None:
        if not name or not name.strip():
            return None

        cache_key = self._cache_key(name)
        if await self._store.exists(cache_key):
            logger.debug("Game Icon API cache hit: %s", name)
            return await self._store.get(cache_key)

        url = f"{self._base_url}/api/game/{quote(name, safe='')}/icon.png"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(url)
        except Exception as exc:
            logger.warning("Game Icon API request failed for %r: %s", name, exc)
            return None

        if r.status_code == 404:
            logger.info("Game Icon API: not found for %r", name)
            return None
        if r.status_code != 200:
            logger.warning("Game Icon API returned %d for %r", r.status_code, name)
            return None

        icon_bytes = r.content
        await self._store.put(cache_key, icon_bytes, r.headers.get("content-type", "image/png"))
        logger.info("Game Icon API: resolved %r via %s (%d bytes)",
                    name, r.headers.get("x-game-store", "?"), len(icon_bytes))
        return icon_bytes
