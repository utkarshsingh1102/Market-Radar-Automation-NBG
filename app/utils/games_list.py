"""
Builds a copy-friendly markdown list of all games in a project.

Format:
    1. [Game Name](store_url) by Publisher
    2. ...

If a draft is missing its publisher, this module refetches it from the iTunes
Lookup API (App Store) or google-play-scraper (Play Store) and writes it back
into the draft state file so future calls are fast.

Publisher names are lightly normalised: comma spacing fixed, recognised brand
casing preserved (GOODROID, MagicLab, MeloDonG, LolTap, GamesTown, RAKUNiK),
known corporate suffixes kept uppercase (LLC, GMBH, AB).
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import re
from pathlib import Path

import httpx

from app.models.project import Project
from app.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

_KNOWN_BRANDS_KEEP = {"GOODROID", "MagicLab", "MeloDonG", "LolTap", "GamesTown", "RAKUNiK"}
_ALL_CAPS_KEEP = {"LLC", "GMBH", "AB"}


def _fix_publisher(p: str | None) -> str | None:
    if not p:
        return None
    p = re.sub(r",(?=\S)", ", ", p.strip())
    parts = re.split(r"(\s+|,)", p)
    out: list[str] = []
    for tok in parts:
        if not tok or tok.isspace() or tok == ",":
            out.append(tok)
            continue
        bare = tok.rstrip(".,").upper()
        if bare in _ALL_CAPS_KEEP:
            out.append(tok.upper())
            continue
        matched_brand = next((b for b in _KNOWN_BRANDS_KEEP if bare.startswith(b.upper())), None)
        if matched_brand:
            suffix = tok[len(matched_brand):]
            out.append(matched_brand + suffix)
            continue
        if any(c.isupper() for c in tok[1:]) and any(c.islower() for c in tok):
            out.append(tok)  # camelCase brand, leave alone
        else:
            out.append(tok.title())
    return "".join(out)


def _clean_title(t: str) -> str:
    return t.rstrip("：:").rstrip()


def _store_url(state: dict) -> str:
    app_id = state.get("store_app_id", "")
    stype = state.get("store_type", "")
    slug = state.get("store_slug", "")
    if stype == "appstore" and app_id and slug:
        nid = app_id.replace("ios_", "")
        return f"https://apps.apple.com/us/app/{slug}/id{nid}"
    if stype == "playstore" and app_id:
        return f"https://play.google.com/store/apps/details?id={app_id}"
    return ""


async def _fetch_publisher(state: dict) -> str | None:
    """Refetch publisher from iTunes Lookup or Play Store. Returns None on miss."""
    app_id = state.get("store_app_id", "")
    stype = state.get("store_type", "")
    if stype == "appstore":
        nid = app_id.replace("ios_", "")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"https://itunes.apple.com/lookup?id={nid}")
                data = r.json()
                if data.get("resultCount", 0) > 0:
                    return data["results"][0].get("artistName")
        except Exception as e:
            logger.warning("iTunes lookup failed for %s: %s", nid, e)
    elif stype == "playstore" and app_id:
        try:
            from google_play_scraper import app as gplay_app
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, functools.partial(gplay_app, app_id, lang="en", country="us"),
            )
            return info.get("developer")
        except Exception as e:
            logger.warning("Play Store lookup failed for %s: %s", app_id, e)
    return None


async def build_games_list(
    project: Project,
    storage_root: Path,
    orchestrator: Orchestrator | None = None,
) -> str:
    """
    Return a markdown list of all games in a project.
    Auto-fetches and persists any missing publishers.
    """
    drafts_dir = storage_root / "drafts"
    lines: list[str] = []

    for slide in project.slides:
        state_path = drafts_dir / slide.draft_id / "state.json"
        if not state_path.exists():
            lines.append(slide.title)
            continue

        state = json.loads(state_path.read_text())
        name = _clean_title(state.get("game_name", "") or slide.title)
        pub_raw = state.get("publisher")
        attempted_fetch = False

        if not pub_raw:
            attempted_fetch = True
            fetched = await _fetch_publisher(state)
            if fetched:
                state["publisher"] = fetched
                state_path.write_text(json.dumps(state, indent=2, default=str))
                pub_raw = fetched

        pub = _fix_publisher(pub_raw)
        if pub:
            lines.append(f"{name} by {pub}")
        elif attempted_fetch:
            lines.append(f"{name} — publisher unavailable, app removed from store")
        else:
            lines.append(name)

    return "\n".join(lines)
