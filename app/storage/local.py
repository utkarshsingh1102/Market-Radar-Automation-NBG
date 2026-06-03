"""Local-filesystem implementation of :class:`AssetStore`.

Keys map to paths under ``root`` (``settings.storage_root``). The FastAPI app
mounts ``root`` at ``/storage`` (see ``app/main.py``), so a key's public URL is
just ``/storage/<key>``.
"""
from __future__ import annotations

import os
from pathlib import Path

import aiofiles

from app.storage.base import AssetStore


class LocalAssetStore(AssetStore):
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ── path helpers ───────────────────────────────────────────────────────────
    def _path(self, key: str) -> Path:
        # Keys always use forward-slash separators; normalise for the OS and
        # strip any leading slash so the key stays relative to root.
        rel = Path(key.lstrip("/"))
        return self.root / rel

    # ── AssetStore interface ────────────────────────────────────────────────────
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        # content_type is irrelevant for the filesystem backend.
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return self.public_url(key)

    async def get(self, key: str) -> bytes:
        async with aiofiles.open(self._path(key), "rb") as f:
            return await f.read()

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    async def delete_prefix(self, prefix: str) -> None:
        base = self._path(prefix)
        # Prefix may name a directory (e.g. "drafts/<id>/") or a key stem.
        if base.is_dir():
            _rmtree(base)
            return
        parent = base.parent
        if not parent.is_dir():
            return
        stem = base.name
        for child in parent.iterdir():
            if child.name.startswith(stem):
                if child.is_dir():
                    _rmtree(child)
                else:
                    child.unlink(missing_ok=True)

    def public_url(self, key: str) -> str:
        return f"/storage/{key.lstrip('/')}"


def _rmtree(path: Path) -> None:
    """Recursively delete a directory tree without importing shutil at top level."""
    for entry in path.iterdir():
        if entry.is_dir():
            _rmtree(entry)
        else:
            entry.unlink(missing_ok=True)
    os.rmdir(path)
