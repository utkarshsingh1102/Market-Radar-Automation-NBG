"""Asset storage package.

Exposes the :class:`AssetStore` interface and the local-filesystem
implementation. All persistence in the app goes through this layer — never
write directly to ``storage/`` (see CLAUDE.md design principle #2).
"""
from app.storage.base import AssetStore
from app.storage.local import LocalAssetStore

__all__ = ["AssetStore", "LocalAssetStore"]
