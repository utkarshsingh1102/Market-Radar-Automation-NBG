"""AssetStore interface.

Storage is an interface (CLAUDE.md design principle #2): the rest of the app
addresses assets by string *key* (e.g. ``drafts/<id>/screenshot.png``) and
never touches the filesystem directly. ``LocalAssetStore`` backs keys with the
local ``storage/`` directory now; an ``S3AssetStore`` can be swapped in later
(PLAN.md phase 8) by implementing this same contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AssetStore(ABC):
    """Key/value blob store for rendered assets, uploads and caches."""

    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        """Store ``data`` under ``key`` and return its public URL.

        ``content_type`` is advisory metadata (used by object stores such as
        S3); the local backend ignores it.
        """

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Return the bytes stored under ``key``. Raises if the key is absent."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return ``True`` if ``key`` has been stored."""

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> None:
        """Delete every key beginning with ``prefix`` (e.g. ``drafts/<id>/``)."""

    @abstractmethod
    def public_url(self, key: str) -> str:
        """Return the URL a browser can fetch ``key`` from."""
