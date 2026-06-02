# Inspiration Icon Resolution Strategy

The goal is: given a **game/concept name** (and optionally a publisher), produce a **512×512 PNG icon** to use in a layout. The strategy is a layered fallback chain — try the cheapest, highest-quality source first, then degrade gracefully.

## The fallback chain

```
1. iTunes Search API  (App Store)
       ↓ miss
2. google-play-scraper (Play Store)
       ↓ miss
3. Supabase theme catalogue (curated keyword → image map)
       ↓ miss
4. DALL-E 3 generation     (optional, gated by OPENAI_API_KEY)
       ↓ miss
5. Concept placeholder     (programmatic Pillow icon with initials)
```

Every step writes to a single shared cache so we never re-fetch the same thing twice.

---

## Step 1 — iTunes Search API (App Store)

- **Endpoint:** `GET https://itunes.apple.com/search?term=<query>&entity=software&limit=5`
- **No auth required.**
- Take the top result's `artworkUrl512` (fall back to `artworkUrl100`), download it.
- **Rate limit ~20 req/min per IP** — implement a sliding-window limiter. Keep a list of timestamps from the last 60s, sleep if you've hit the cap.
- Use the search query verbatim (`"<game name> by <publisher>"` if publisher known).

Why first: highest-quality icons (512px), no auth, fast.

## Step 2 — Play Store

- Use `google-play-scraper` Python package (`from google_play_scraper import search`).
- It's a **synchronous** library — wrap calls in `asyncio.get_event_loop().run_in_executor(...)` so they don't block.
- `search(query, n_hits=5, lang="en", country="us")` returns dicts with an `icon` URL — download that.

## Step 3 — Supabase curated catalogue

- Manually-curated XLSX file with rows of `(theme_name, supabase_public_url)`. ~64 themes like `Coin`, `Castle`, `Zombie`, `Planets`, `Farm`, `Space / Astronaut`.
- Loaded once at startup with `openpyxl`.
- **Matching:** split query and theme name into word-sets (split on `[\s:/\-_,]+`), score = exact-word overlap + partial substring matches (≥3 chars). Score must be ≥1; tie-break on longer theme name.
- Download AVIF, convert to PNG via Pillow `Image.open(io.BytesIO(...)).convert("RGBA")`, resize 512×512.

This step is what saves you from generic icons when iTunes/Play miss but the concept is recognizable (e.g., "Castle Defense" → matches `Castle`).

## Step 4 — DALL-E 3 (optional)

- `POST https://api.openai.com/v1/images/generations` with `model="dall-e-3"`, `size="1024x1024"`, `response_format="url"`.
- Takes the URL returned, downloads the PNG, resizes to 512.
- The prompt template heavily biases toward **single hero subject, restrained 2-3 color palette, full-bleed background, no text/UI/borders** — important so it doesn't render an "icon-within-an-icon" with rounded corners baked in (the OS applies its own corners).

Skip this layer if you don't want to pay for generation.

## Step 5 — Concept placeholder

- Pure Pillow: 512×512 rounded-corner-clipped solid background + the name's **initials** in white bold text.
- Background colour deterministic from `hashlib.md5(name.lower())` indexed into a 12-colour palette → same name always gets the same colour.
- This step is guaranteed to succeed — never returns `None`.

---

## Caching layer (critical)

Every resolver computes a cache key like `cache/icons/<sha256(name.lower())>.png`. Each prefixes with its source so different sources don't collide:

```
cache/icons/<hash>.png            # iTunes
cache/icons/gplay_<hash>.png      # Play Store
cache/icons/supabase_theme_<h>    # Supabase
cache/icons/dalle_<hash>.png      # DALL-E
cache/icons/concept_<hash>.png    # Concept
```

Pattern: every resolver calls `await store.exists(cache_key)` first, returns the cached bytes if found. Only on miss does it hit the network. This is essential — without it you burn API quota on every render.

---

## Architecture pattern

Each resolver implements the same interface:

```python
class IconResolver:
    async def resolve(self, query: str) -> bytes | None:
        ...
```

Returns PNG bytes on success, `None` on miss. The orchestrator wires them in order, calling each `.resolve()` sequentially until one returns non-None. The placeholder is the last one and never returns None.

---

## Two source-types in the input

Inspirations come in as either:

- **`auto`** — has a `query` string, hits iTunes/Play first (steps 1→2→3→4 → fail = `needs_upload` status).
- **`concept`** — has just a `name` (e.g., "Idle", "Merge", "Holes"). Skips iTunes/Play, goes straight to Supabase theme → DALL-E → concept placeholder.

The discriminator is the `source` field on the input model.

---

## Why this order

| Source | Quality | Cost | Speed | Hit rate |
|---|---|---|---|---|
| iTunes | High (512px, official) | Free | ~300ms | High for real games |
| Play Store | High | Free | ~500ms | High for Android-only |
| Supabase | Curated quality | Free | ~100ms | Medium (covers themes) |
| DALL-E | Variable | $0.04/image | ~10s | Always succeeds if key set |
| Concept | Low (just initials) | Free | <10ms | 100% |

Order = quality × hit-rate ÷ cost.

---

## Gotchas to flag

1. **Rate-limit iTunes** — without it you get 403'd in batches.
2. **Run google-play-scraper in a thread pool** — it's blocking.
3. **AVIF needs Pillow ≥10** with libavif support.
4. **DALL-E prompt matters a lot** — without "no rounded corners, full-bleed background" it outputs an icon-within-an-icon.
5. **Cache is non-negotiable.** A naive "always re-fetch" makes batch rendering 50× slower and DALL-E 50× more expensive.

---

That's the complete strategy. The code lives in `app/resolvers/{itunes,playstore,combined,supabase_theme,dalle,concept}.py` and is wired in `app/orchestrator.py::_resolve_icon` and `_refresh_missing_icons`.
