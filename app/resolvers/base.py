"""Base interface for icon resolvers."""
from __future__ import annotations


class IconResolver:
    async def resolve(self, query: str) -> bytes | None:
        raise NotImplementedError
