#!/usr/bin/env python3
"""
provenance.py — Automated Forensic History Generator for Physical Game Objects
Lord of the Files | Extracted Minds Lab
Usage: python provenance.py "7 Sins" PC [--region EUR] [--config keys.json]
Output: 7_Sins_PC_provenance.json
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG & KEYS
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG_PATH = Path(__file__).parent / "provenance_keys.json"

CONFIG_TEMPLATE = {
    "igdb_client_id": "",       # Twitch Dev App — https://dev.twitch.tv/console/apps
    "igdb_client_secret": "",   # same app
    "mobygames_api_key": "",    # https://www.mobygames.com/info/api/
    "youtube_api_key": "",      # Google Cloud Console — YouTube Data API v3
    "ebay_app_id": "",          # https://developer.ebay.com/ — Browse API (free tier)
    "rawg_api_key": "",         # https://rawg.io/apidocs
}


def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"[provenance] No config found at {path}. Creating template...")
        path.write_text(json.dumps(CONFIG_TEMPLATE, indent=2))
        print(f"[provenance] Fill in {path} with your API keys and re-run.")
        sys.exit(1)
    return json.loads(path.read_text())


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

PLATFORM_MAP = {
    "PC":       {"igdb_slug": "pc",        "moby_id": 3,   "ebay_term": "PC",           "rawg_id": 4},
    "PS2":      {"igdb_slug": "ps2",       "moby_id": 7,   "ebay_term": "PS2 PAL",      "rawg_id": 15},
    "PS3":      {"igdb_slug": "ps3",       "moby_id": 81,  "ebay_term": "PS3",          "rawg_id": 16},
    "Xbox":     {"igdb_slug": "xbox",      "moby_id": 13,  "ebay_term": "Xbox original","rawg_id": 14},
    "Xbox 360": {"igdb_slug": "xbox360",   "moby_id": 69,  "ebay_term": "Xbox 360",     "rawg_id": 1},
    "Wii":      {"igdb_slug": "wii",       "moby_id": 82,  "ebay_term": "Wii",          "rawg_id": 11},
    "Dreamcast":{"igdb_slug": "dc",        "moby_id": 8,   "ebay_term": "Dreamcast",    "rawg_id": 106},
    "PS1":      {"igdb_slug": "ps1",       "moby_id": 6,   "ebay_term": "PS1 PAL",      "rawg_id": 27},
}

REGION_MAP = {
    "EUR": "PAL",
    "PAL": "PAL",
    "USA": "NTSC",
    "NTSC": "NTSC",
    "JAP": "NTSC-J",
}


def slugify(text: str) -> str:
    return re.sub(r"[^\w]", "_", text).strip("_")


DEFAULT_HEADERS = {
    "User-Agent": "provenance/0.1 (lord-of-the-files; forensic game cataloguing; "
                  "https://github.com/intima-mentis/lordofthefiles)"
}


def safe_get(url: str, params: dict = None, headers: dict = None,
             timeout: int = 10, retries: int = 2) -> requests.Response | None:
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 5))
                print(f"  [rate limit] sleeping {wait}s...")
                time.sleep(wait)
                continue
            return r
        except requests.RequestException as e:
            if attempt == retries:
                print(f"  [warn] GET {url} failed: {e}")
                return None
            time.sleep(1)
    return None


def safe_post(url: str, data: dict = None, headers: dict = None,
              timeout: int = 10) -> requests.Response | None:
    try:
        r = requests.post(url, data=data, headers=headers, timeout=timeout)
        return r
    except requests.RequestException as e:
        print(f"  [warn] POST {url} failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# IGDB — AUTH + QUERY
# ─────────────────────────────────────────────────────────────────────────────

_igdb_token_cache: dict = {}


def igdb_token(client_id: str, client_secret: str) -> str | None:
    global _igdb_token_cache
    if _igdb_token_cache.get("token"):
        return _igdb_token_cache["token"]
    r = safe_post(
        "https://id.twitch.tv/oauth2/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    )
    if r and r.status_code == 200:
        token = r.json().get("access_token")
        _igdb_token_cache["token"] = token
        return token
    return None


def igdb_query(endpoint: str, body: str, client_id: str, token: str) -> list:
    r = requests.post(
        f"https://api.igdb.com/v4/{endpoint}",
        headers={
            "Client-ID": client_id,
            "Authorization": f"Bearer {token}",
        },
        data=body,
        timeout=10,
    )
    if r.status_code == 200:
        return r.json()
    print(f"  [igdb] {endpoint} returned {r.status_code}: {r.text[:200]}")
    return []


def igdb_find_game(title: str, platform_slug: str, client_id: str, token: str) -> dict | None:
    results = igdb_query(
        "games",
        f'search "{title}"; fields id,name,first_release_date,involved_companies,similar_games,'
        f'summary,genres,platforms,url,status; where platforms.slug = "{platform_slug}"; limit 5;',
        client_id, token
    )
    if not results:
        # fallback: search without platform filter
        results = igdb_query(
            "games",
            f'search "{title}"; fields id,name,first_release_date,involved_companies,'
            f'similar_games,summary,genres,platforms,url,status; limit 5;',
            client_id, token
        )
    return results[0] if results else None


def igdb_similar_games(similar_ids: list, client_id: str, token: str) -> list:
    if not similar_ids:
        return []
    ids_str = ",".join(str(i) for i in similar_ids[:8])
    results = igdb_query(
        "games",
        f"fields name,url; where id = ({ids_str});",
        client_id, token
    )
    return [g.get("name") for g in results if g.get("name")]


def igdb_companies(involved_ids: list, client_id: str, token: str) -> dict:
    """Returns {developer: str, publisher: str}"""
    if not involved_ids:
        return {}
    ids_str = ",".join(str(i) for i in involved_ids)
    results = igdb_query(
        "involved_companies",
        f"fields company.name,developer,publisher; where id = ({ids_str}); limit 20;",
        client_id, token
    )
    devs, pubs = [], []
    for entry in results:
        name = entry.get("company", {}).get("name", "")
        if entry.get("developer"):
            devs.append(name)
        if entry.get("publisher"):
            pubs.append(name)
    return {"developers": devs, "publishers": pubs}


# ─────────────────────────────────────────────────────────────────────────────
# MOBYGAMES — GAME INFO + CREDITS + SCREENSHOTS
# ─────────────────────────────────────────────────────────────────────────────

MOBY_BASE = "https://api.mobygames.com/v1"


# Keywords that indicate special/non-standard editions — prefer standard release
EDITION_KEYWORDS = [
    "hardened", "prestige", "collector", "limited", "special", "premium",
    "deluxe", "gold", "platinum edition", "game of the year edition", "goty",
    "complete edition", "definitive edition", "remastered", "bundle"
]


def moby_find_game(title: str, platform_id: int, api_key: str) -> dict | None:
    """
    Find game on MobyGames, preferring standard retail release over special editions.
    """
    r = safe_get(
        f"{MOBY_BASE}/games",
        params={"title": title, "platform": platform_id, "api_key": api_key, "limit": 10}
    )
    if not (r and r.status_code == 200):
        return None

    games = r.json().get("games", [])
    if not games:
        return None

    # Prefer exact title match or standard edition over special editions
    title_lower = title.lower()
    standard = []
    special = []

    for game in games:
        game_title = game.get("title", "").lower()
        is_special = any(kw in game_title for kw in EDITION_KEYWORDS)
        # Exact match is always preferred
        if game_title == title_lower:
            return game
        if is_special:
            special.append(game)
        else:
            standard.append(game)

    # Return first standard edition, fall back to special if nothing else
    return (standard or special or games)[0]


def moby_credits(game_id: int, api_key: str) -> dict:
    """Returns {composer: str | None, director: str | None, raw: list}"""
    r = safe_get(f"{MOBY_BASE}/games/{game_id}/credits", params={"api_key": api_key})
    if not (r and r.status_code == 200):
        return {"composer": None, "director": None, "raw": []}

    credits_data = r.json()
    composer, director = None, None
    raw_list = []

    for section in credits_data.get("credits", []):
        for person in section.get("credits", []):
            name = person.get("person", {}).get("name", "")
            role = person.get("job", {}).get("job_name", "")
            raw_list.append({"name": name, "role": role})
            role_lower = role.lower()
            if any(kw in role_lower for kw in ("composer", "music", "sound design", "audio")):
                composer = composer or f"{name} ({role})"
            if any(kw in role_lower for kw in ("director", "lead designer")):
                director = director or f"{name} ({role})"

    return {"composer": composer, "director": director, "raw": raw_list}


def moby_screenshots(game_id: int, platform_id: int, api_key: str) -> list:
    r = safe_get(
        f"{MOBY_BASE}/games/{game_id}/platforms/{platform_id}/screenshots",
        params={"api_key": api_key, "limit": 6}
    )
    if r and r.status_code == 200:
        return [s.get("image") for s in r.json().get("screenshots", []) if s.get("image")]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# WIKIPEDIA — SUMMARY + UNITS SOLD + REGIONAL INFO
# ─────────────────────────────────────────────────────────────────────────────

WIKI_API = "https://en.wikipedia.org/api/rest_v1"
WIKI_ACTION = "https://en.wikipedia.org/w/api.php"


def wiki_summary(title: str) -> dict | None:
    candidates = [
        f"{title} (video game)",
        f"{title} (game)",
        title,
    ]
    best_non_game = None
    for candidate in candidates:
        r = safe_get(f"{WIKI_API}/page/summary/{requests.utils.quote(candidate)}")
        if not (r and r.status_code == 200):
            continue
        data = r.json()
        description = data.get("description", "").lower()
        extract = data.get("extract", "").lower()
        if "disambiguation" in description:
            continue
        # Prefer pages that are clearly about a video game
        is_game_page = any(kw in description or kw in extract[:200]
                           for kw in ("video game", "action game", "role-playing",
                                      "adventure game", "platform game", "developed by",
                                      "published by", "video gaming"))
        if is_game_page:
            return data
        # Keep as fallback if nothing better found
        if best_non_game is None:
            best_non_game = data
    return best_non_game


def wiki_infobox(title: str) -> dict:
    """
    Scrape infobox fields and sales sections from wikitext.
    Handles both:
    - Infobox field: | units sold = X
    - Narrative Sales section: == Sales == ... sold X copies
    """
    # Try with and without (video game) suffix
    candidates = [f"{title} (video game)", title]
    wikitext = ""

    for page_title in candidates:
        r = safe_get(
            WIKI_ACTION,
            params={
                "action": "query",
                "titles": page_title,
                "prop": "revisions",
                "rvprop": "content",
                "format": "json",
                "rvslots": "main",
            }
        )
        if not (r and r.status_code == 200):
            continue
        pages = r.json().get("query", {}).get("pages", {})
        for page in pages.values():
            # -1 means page not found in Wikipedia
            if str(page.get("pageid", -1)) == "-1":
                continue
            wikitext = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
            if wikitext:
                break
        if wikitext:
            break

    if not wikitext:
        return {}

    def parse_wiki_field(text: str, field: str) -> str | None:
        """Parse a wikitext infobox field, handling templates and wiki links."""
        pattern = rf"\|\s*(?:{field})\s*=\s*(.+?)(?=\n\s*\||\n\s*\}}|\Z)"
        m2 = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not m2:
            return None
        raw = m2.group(1).strip()
        raw = re.sub(r"\{\{(?:Unbulleted|Plain)\s*list\|", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\[\[(?:[^\|\]]*\|)?([^\]]+)\]\]", r"\1", raw)
        raw = re.sub(r"\}\}", "", raw)
        raw = re.sub(r"\{\{[^}]*\}?", "", raw)
        raw = re.sub(r"<br\s*/?>", ", ", raw, flags=re.IGNORECASE)
        raw = re.sub(r"<[^>]+>", "", raw)
        raw = re.sub(r"[|\n]+", ", ", raw)
        raw = re.sub(r",\s*,+", ",", raw)
        raw = re.sub(r"^\s*,\s*|\s*,\s*$", "", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        return raw if raw else None

    result = {}

    # Credits from infobox
    composer = parse_wiki_field(wikitext, "composer|music")
    if composer:
        result["composer"] = composer

    director = parse_wiki_field(wikitext, "director|lead designer|game director")
    if director:
        result["director"] = director

    designer = parse_wiki_field(wikitext, "designer|lead designer")
    if designer:
        result["designer"] = designer

    # Method 1: infobox field | units sold = X
    m = re.search(r"\|\s*units?\s*sold\s*=\s*([^\n\|]+)", wikitext, re.IGNORECASE)
    if m:
        val = re.sub(r"<[^>]+>", "", m.group(1))  # strip HTML tags
        val = re.sub(r"\{\{[^}]+\}\}", "", val)    # strip wiki templates
        val = val.strip()
        if val:
            result["units_sold"] = val

    # Method 2: Sales section narrative — extract first number mentioned
    # after "== Sales ==" heading
    if "units_sold" not in result:
        sales_match = re.search(
            r"==\s*Sales?\s*==(.+?)(?===|\Z)",
            wikitext, re.IGNORECASE | re.DOTALL
        )
        if sales_match:
            sales_text = sales_match.group(1)
            # Find first number (e.g. "sold over 500,000 copies" or "17.5 million")
            num_match = re.search(
                r"sold[^\d]*?([\d,\.]+\s*(?:million|billion|thousand)?)\s*(?:copies|units)",
                sales_text, re.IGNORECASE
            )
            if num_match:
                result["units_sold"] = num_match.group(1).strip()
                result["units_sold_source"] = "wikipedia_sales_section"

    # Regional differences / censorship section
    if re.search(r"==\s*(regional|censorship|version differences)", wikitext, re.IGNORECASE):
        result["has_regional_section"] = True
    elif "regional" in wikitext.lower() or "censorship" in wikitext.lower():
        result["has_regional_section"] = True

    return result


# ─────────────────────────────────────────────────────────────────────────────
# YOUTUBE — ANNOUNCEMENT DATE (oldest trailer)
# ─────────────────────────────────────────────────────────────────────────────

YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"


def youtube_announcement_date(title: str, api_key: str,
                              release_date: str = None) -> str | None:
    """
    Returns ISO date string of oldest trailer found before game release date.
    Uses publishedBefore parameter to restrict YouTube search to pre-release period.
    Games released before 2005 (before YouTube existed) will always return None.
    """
    # YouTube launched April 2005 — skip for older games
    if release_date and release_date < "2005-05-01":
        return None

    params = {
        "q": f"{title} official trailer",
        "type": "video",
        "order": "date",
        "part": "snippet",
        "maxResults": 25,
        "key": api_key,
    }

    # Restrict search to videos published before release date
    # YouTube API requires RFC 3339 format: 2010-11-09T00:00:00Z
    if release_date:
        params["publishedBefore"] = f"{release_date}T00:00:00Z"

    r = safe_get(YT_SEARCH, params=params)
    if not (r and r.status_code == 200):
        return None

    items = r.json().get("items", [])
    if not items:
        return None

    dates = []
    for item in items:
        published = item.get("snippet", {}).get("publishedAt", "")
        if published:
            dates.append(published[:10])

    if not dates:
        return None

    dates.sort()
    return dates[0]  # oldest pre-release video


# ─────────────────────────────────────────────────────────────────────────────
# EBAY — SCARCITY (Browse API)
# ─────────────────────────────────────────────────────────────────────────────

EBAY_BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# eBay OAuth token (App-only, server-to-server)
_ebay_token_cache: dict = {}


def ebay_token(app_id: str) -> str | None:
    """App-level OAuth token (no user auth needed for Browse API)."""
    global _ebay_token_cache
    if _ebay_token_cache.get("token"):
        return _ebay_token_cache["token"]

    import base64
    # Note: for real use you also need client_secret (cert_id).
    # Simplified here — extend by adding ebay_cert_id to config.
    print("  [ebay] OAuth requires cert_id in config — skipping live eBay data")
    return None


def ebay_scarcity(title: str, platform: str, region: str, app_id: str) -> dict:
    """Returns {active_listings: int, price_range: str, query_used: str}"""
    token = ebay_token(app_id)
    if not token:
        return {"active_listings": None, "price_range": None, "note": "eBay token not configured"}

    platform_info = PLATFORM_MAP.get(platform, {})
    ebay_term = platform_info.get("ebay_term", platform)
    region_label = REGION_MAP.get(region, "PAL")
    query = f"{title} {ebay_term} {region_label}"

    r = safe_get(
        EBAY_BROWSE,
        params={"q": query, "limit": 50, "filter": "buyingOptions:{FIXED_PRICE|AUCTION}"},
        headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_DE"}
    )
    if not (r and r.status_code == 200):
        return {"active_listings": None, "price_range": None, "query_used": query}

    items = r.json().get("itemSummaries", [])
    prices = []
    for item in items:
        p = item.get("price", {}).get("value")
        if p:
            try:
                prices.append(float(p))
            except ValueError:
                pass

    price_range = None
    if prices:
        price_range = f"€{min(prices):.2f}–€{max(prices):.2f} (avg €{sum(prices)/len(prices):.2f})"

    return {
        "active_listings": len(items),
        "price_range": price_range,
        "query_used": query,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }



# ─────────────────────────────────────────────────────────────────────────────────
# RAWG — METACRITIC, TAGS, RATINGS, STORES
# ─────────────────────────────────────────────────────────────────────────────────

RAWG_BASE = "https://api.rawg.io/api"

RAWG_STORE_NAMES = {
    1: "Steam",
    2: "Xbox Store",
    3: "PlayStation Store",
    4: "App Store",
    5: "GOG",
    6: "Nintendo Store",
    7: "Xbox 360 Store",
    8: "Google Play",
    9: "itch.io",
    11: "Epic Games",
}


def rawg_find_game(title: str, platform_id: int, api_key: str) -> dict | None:
    """Search RAWG for a game, filtered by platform. Returns game detail dict or None."""
    # Search endpoint
    r = safe_get(
        f"{RAWG_BASE}/games",
        params={
            "search": title,
            "platforms": platform_id,
            "search_exact": "false",
            "page_size": 5,
            "key": api_key,
        }
    )
    if not (r and r.status_code == 200):
        return None

    results = r.json().get("results", [])
    if not results:
        # Fallback: search without platform filter
        r2 = safe_get(
            f"{RAWG_BASE}/games",
            params={"search": title, "page_size": 5, "key": api_key}
        )
        if r2 and r2.status_code == 200:
            results = r2.json().get("results", [])

    if not results:
        return None

    # Prefer closest title match
    title_lower = title.lower()
    for game in results:
        if game.get("name", "").lower() == title_lower:
            game_id = game["id"]
            break
    else:
        game_id = results[0]["id"]

    # Fetch full detail record (includes stores, tags, metacritic per platform)
    r_detail = safe_get(
        f"{RAWG_BASE}/games/{game_id}",
        params={"key": api_key}
    )
    if r_detail and r_detail.status_code == 200:
        return r_detail.json()

    return results[0]


def rawg_extract(rawg_game: dict, platform_id: int) -> dict:
    """
    Extract provenance-relevant fields from RAWG game detail.
    Returns a flat dict consumed by build_layer_identity and build_layer_survival.
    """
    if not rawg_game:
        return {}

    result = {}

    # Metacritic — overall + per-platform if available
    metacritic = rawg_game.get("metacritic")
    if metacritic:
        result["metacritic_score"] = metacritic
        result["metacritic_url"] = rawg_game.get("metacritic_url")

    # Per-platform Metacritic score
    for plat in rawg_game.get("metacritic_platforms", []):
        if plat.get("platform", {}).get("platform", {}).get("id") == platform_id:
            result["metacritic_score_platform"] = plat.get("metascore")
            result["metacritic_url_platform"] = plat.get("url")
            break

    # RAWG community rating
    rating = rawg_game.get("rating")
    ratings_count = rawg_game.get("ratings_count")
    if rating:
        result["rawg_rating"] = round(rating, 2)
        result["rawg_ratings_count"] = ratings_count

    # Average playtime (hours)
    playtime = rawg_game.get("playtime")
    if playtime:
        result["playtime_hours"] = playtime

    # Tags — top 8 by relevance
    tags = rawg_game.get("tags", [])
    if tags:
        result["tags"] = [t["name"] for t in tags[:8]]

    # Genres
    genres = rawg_game.get("genres", [])
    if genres:
        result["genres_rawg"] = [g["name"] for g in genres]

    # Official website
    website = rawg_game.get("website")
    if website:
        result["official_website"] = website

    # Stores — real verified links for Layer IX
    stores = []
    for s in rawg_game.get("stores", []):
        store_id = s.get("store", {}).get("id")
        store_url = s.get("url")
        store_name = RAWG_STORE_NAMES.get(store_id, s.get("store", {}).get("name", ""))
        if store_name and store_url:
            stores.append({"store": store_name, "url": store_url})
    if stores:
        result["stores"] = stores

    result["rawg_id"] = rawg_game.get("id")
    result["rawg_url"] = f"https://rawg.io/games/{rawg_game.get('slug', '')}"

    return result

# ─────────────────────────────────────────────────────────────────────────────
# LAYER ASSEMBLERS — the 10 layers
# ─────────────────────────────────────────────────────────────────────────────

def build_layer_identity(title: str, platform: str, region: str,
                          igdb_game: dict | None, moby_game: dict | None,
                          rawg_data: dict | None = None) -> dict:
    """Layer I — Identity"""
    layer = {
        "layer": "I · IDENTITY",
        "title": title,
        "platform": platform,
        "region": region,
        "region_standard": REGION_MAP.get(region.upper(), region),
    }

    if igdb_game:
        ts = igdb_game.get("first_release_date")
        if ts:
            layer["release_date"] = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        layer["igdb_id"] = igdb_game.get("id")
        layer["igdb_url"] = igdb_game.get("url")

    if moby_game:
        layer["moby_id"] = moby_game.get("game_id")
        layer["moby_url"] = moby_game.get("moby_url")
        # description from MobyGames often has PEGI info
        desc = moby_game.get("description", "")
        if desc:
            layer["moby_description_excerpt"] = desc[:300]

    if rawg_data:
        if rawg_data.get("metacritic_score"):
            layer["metacritic_score"] = rawg_data["metacritic_score"]
            if rawg_data.get("metacritic_score_platform"):
                layer["metacritic_score_platform"] = rawg_data["metacritic_score_platform"]
            if rawg_data.get("metacritic_url"):
                layer["metacritic_url"] = rawg_data["metacritic_url"]
        if rawg_data.get("rawg_rating"):
            layer["rawg_rating"] = rawg_data["rawg_rating"]
            layer["rawg_ratings_count"] = rawg_data.get("rawg_ratings_count")
        if rawg_data.get("playtime_hours"):
            layer["playtime_hours_avg"] = rawg_data["playtime_hours"]
        if rawg_data.get("tags"):
            layer["tags"] = rawg_data["tags"]
        if rawg_data.get("genres_rawg"):
            layer["genres"] = rawg_data["genres_rawg"]
        if rawg_data.get("rawg_id"):
            layer["rawg_id"] = rawg_data["rawg_id"]
            layer["rawg_url"] = rawg_data["rawg_url"]

    return layer


def build_layer_origin(igdb_companies_data: dict, igdb_game: dict | None,
                        wiki_data: dict | None) -> dict:
    """Layer II — Origin (developer / publisher / announcement)"""
    layer = {
        "layer": "II · ORIGIN",
        "developers": igdb_companies_data.get("developers", []),
        "publishers": igdb_companies_data.get("publishers", []),
    }

    if wiki_data:
        layer["wiki_summary"] = wiki_data.get("extract", "")[:500]
        layer["wiki_url"] = wiki_data.get("content_urls", {}).get("desktop", {}).get("page")

    return layer


def build_layer_human(credits: dict, wiki_ib: dict = None) -> dict:
    """
    Layer III — Human (director, composer, key staff).
    Uses MobyGames credits first, falls back to Wikipedia infobox.
    """
    composer = credits.get("composer")
    director = credits.get("director")
    sources = []

    if composer or director:
        sources.append("MobyGames API")
    
    # Fallback to Wikipedia infobox if MobyGames has nothing
    if wiki_ib:
        if not composer and wiki_ib.get("composer"):
            composer = wiki_ib["composer"]
            sources.append("Wikipedia infobox")
        if not director and wiki_ib.get("director"):
            director = wiki_ib["director"]
            if "Wikipedia infobox" not in sources:
                sources.append("Wikipedia infobox")

    return {
        "layer": "III · HUMAN",
        "director": director or "UNATTRIBUTED",
        "composer": composer or "UNATTRIBUTED",
        "designer": wiki_ib.get("designer") if wiki_ib else None,
        "credits_found": len(credits.get("raw", [])),
        "sources": sources if sources else ["not in public record"],
        "note": f"Sources: {', '.join(sources) if sources else 'not in public record'}",
    }


def build_layer_music(title: str, credits: dict, wiki_ib: dict = None) -> dict:
    """Layer IV — Music / OST. Uses MobyGames credits first, falls back to Wikipedia."""
    composer = credits.get("composer")
    if not composer and wiki_ib:
        composer = wiki_ib.get("composer")
    khinsider_search = f"https://downloads.khinsider.com/search?search={requests.utils.quote(title)}"
    return {
        "layer": "IV · MUSIC",
        "composer": composer or "UNATTRIBUTED",
        "ost_status": "check_manually",
        "khinsider_search": khinsider_search,
        "vgmdb_search": f"https://vgmdb.net/search?q={requests.utils.quote(title)}",
        "note": "VGMdb and khinsider require scraping — not yet automated. Search links generated.",
    }


def build_layer_screenshots(screenshots: list) -> dict:
    """Layer V — Memory (screenshots as visual evidence)"""
    return {
        "layer": "V · SCREENSHOTS",
        "count": len(screenshots),
        "urls": screenshots,
        "source": "MobyGames API",
    }


def build_layer_context(title: str, platform: str, region: str,
                         wiki_infobox_data: dict) -> dict:
    """Layer VI — Context (regional differences, bans, censorship)"""
    layer = {
        "layer": "VI · CONTEXT",
        "region": region,
        "region_standard": REGION_MAP.get(region.upper(), region),
        "has_wikipedia_regional_section": wiki_infobox_data.get("has_regional_section", False),
        "note": "Regional censorship data not in structured DB — check Wikipedia + GameFAQs manually for cuts.",
    }
    return layer


def build_layer_market(title: str, platform: str, region: str,
                        wiki_infobox_data: dict, ebay_data: dict) -> dict:
    """Layer VII — Market (units sold, current price)"""
    return {
        "layer": "VII · MARKET",
        "units_sold": wiki_infobox_data.get("units_sold", "NOT IN PUBLIC RECORD"),
        "ebay_active_listings": ebay_data.get("active_listings"),
        "ebay_price_range": ebay_data.get("price_range"),
        "ebay_query": ebay_data.get("query_used"),
        "ebay_retrieved_at": ebay_data.get("retrieved_at"),
        "note": ebay_data.get("note"),
    }


def build_layer_discovery(similar_games: list) -> dict:
    """Layer VIII — Discovery (similar titles from IGDB)"""
    return {
        "layer": "VIII · DISCOVERY",
        "similar_games_igdb": similar_games,
        "note": "Source: IGDB similar_games field. Reflects algorithmic similarity, not editorial curation.",
    }


def build_layer_survival(title: str, platform: str,
                            rawg_data: dict | None = None) -> dict:
    """Layer IX — Survival (digital availability, patches, emulation status)"""
    gog_search = f"https://www.gog.com/games?query={requests.utils.quote(title)}"
    steam_search = f"https://store.steampowered.com/search/?term={requests.utils.quote(title)}"
    protondb_search = f"https://www.protondb.com/search?q={requests.utils.quote(title)}"

    layer = {
        "layer": "IX · SURVIVAL",
        "emulation_check": "Check PCSX2 compat list for PS2, RPCS3 for PS3.",
    }

    # Use verified store links from RAWG if available
    if rawg_data and rawg_data.get("stores"):
        layer["stores_verified"] = rawg_data["stores"]
        layer["official_website"] = rawg_data.get("official_website")
        layer["note"] = "Store links verified via RAWG."
    else:
        layer["gog_search"] = gog_search
        layer["steam_search"] = steam_search
        layer["note"] = "No verified store links found via RAWG. Search links generated for manual check."

    layer["protondb_search"] = protondb_search

    return layer


def build_layer_verdict(title: str, platform: str, region: str,
                         layers: list) -> dict:
    """Layer X — Verdict (forensic summary for keep/sell/document decision)"""
    return {
        "layer": "X · FORENSIC VERDICT",
        "object": f"{title} — {platform} — {region}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "completeness_notes": [
            "Layer III: Check MobyGames credits section manually if composer shows UNATTRIBUTED",
            "Layer IV: Verify OST status via khinsider + VGMdb links",
            "Layer VI: Check regional differences on Wikipedia + GameFAQs manually",
            "Layer VII: eBay data is live if API key configured, otherwise check manually",
            "Layer IX: Digital availability requires manual GOG/Steam check",
        ],
        "verdict": "PENDING — review layers and add keep/sell/document decision manually",
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_provenance(title: str, platform: str, region: str, config: dict) -> dict:
    print(f"\n[provenance] Starting: {title} | {platform} | {region}")
    print("─" * 60)

    platform_info = PLATFORM_MAP.get(platform, {})
    igdb_slug = platform_info.get("igdb_slug", platform.lower())
    moby_platform_id = platform_info.get("moby_id", 0)

    # ── IGDB
    igdb_game = None
    igdb_similar = []
    igdb_comps = {}
    if config.get("igdb_client_id") and config.get("igdb_client_secret"):
        print("[I] Authenticating with IGDB...")
        token = igdb_token(config["igdb_client_id"], config["igdb_client_secret"])
        if token:
            print("[I] Fetching game record from IGDB...")
            igdb_game = igdb_find_game(title, igdb_slug, config["igdb_client_id"], token)
            if igdb_game:
                print(f"    ✓ Found: {igdb_game.get('name')} (id={igdb_game.get('id')})")
                igdb_comps = igdb_companies(
                    igdb_game.get("involved_companies", []),
                    config["igdb_client_id"], token
                )
                igdb_similar = igdb_similar_games(
                    igdb_game.get("similar_games", []),
                    config["igdb_client_id"], token
                )
            else:
                print("    [warn] IGDB: no match found")
        else:
            print("    [warn] IGDB: authentication failed")
    else:
        print("[I] IGDB keys not configured — skipping")

    # ── MobyGames
    moby_game = None
    moby_credits_data = {"composer": None, "director": None, "raw": []}
    screenshots = []
    if config.get("mobygames_api_key"):
        print("[II] Searching MobyGames...")
        moby_game = moby_find_game(title, moby_platform_id, config["mobygames_api_key"])
        if moby_game:
            gid = moby_game.get("game_id")
            print(f"    ✓ Found: {moby_game.get('title')} (id={gid})")
            print("[III] Fetching credits from MobyGames...")
            moby_credits_data = moby_credits(gid, config["mobygames_api_key"])
            print(f"      composer: {moby_credits_data.get('composer') or 'UNATTRIBUTED'}")
            print("[V] Fetching screenshots from MobyGames...")
            screenshots = moby_screenshots(gid, moby_platform_id, config["mobygames_api_key"])
            print(f"      {len(screenshots)} screenshots found")
        else:
            print("    [warn] MobyGames: no match found")
    else:
        print("[II–V] MobyGames key not configured — skipping")

    # ── Wikipedia
    print("[II/VII] Fetching Wikipedia summary...")
    wiki_data = wiki_summary(title)
    wiki_ib = wiki_infobox(title)
    if wiki_data:
        print(f"    ✓ Wikipedia: {wiki_data.get('title')}")
    else:
        print("    [warn] Wikipedia: no page found")

    # ── YouTube
    announcement_date = None
    if config.get("youtube_api_key"):
        print("[II] Searching YouTube for announcement date...")
        # Pass release_date so we only accept pre-release trailers
        # Games before 2005 will always return None (YouTube didn't exist)
        igdb_release = None
        if igdb_game:
            ts = igdb_game.get("first_release_date")
            if ts:
                igdb_release = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        announcement_date = youtube_announcement_date(
            title, config["youtube_api_key"], release_date=igdb_release
        )
        if announcement_date:
            print(f"    ✓ Oldest pre-release trailer found: {announcement_date}")
        else:
            print("    [warn] YouTube: no pre-release trailer found (expected for pre-2005 games)")
    else:
        print("[II] YouTube API key not configured — skipping announcement date")

    # ── eBay
    ebay_data = {}
    if config.get("ebay_app_id"):
        print("[VII] Querying eBay for active listings...")
        ebay_data = ebay_scarcity(title, platform, region, config["ebay_app_id"])
        if ebay_data.get("active_listings") is not None:
            print(f"    ✓ {ebay_data['active_listings']} listings — {ebay_data.get('price_range')}")
    else:
        print("[VII] eBay App ID not configured — skipping live pricing")

    # ── RAWG
    rawg_data = {}
    if config.get("rawg_api_key"):
        rawg_platform_id = platform_info.get("rawg_id", 0)
        print("[I/IX] Querying RAWG...")
        rawg_game = rawg_find_game(title, rawg_platform_id, config["rawg_api_key"])
        if rawg_game:
            rawg_data = rawg_extract(rawg_game, rawg_platform_id)
            mc = rawg_data.get("metacritic_score")
            rating = rawg_data.get("rawg_rating")
            stores = len(rawg_data.get("stores", []))
            print(f"    ✓ Metacritic: {mc or 'n/a'} | RAWG rating: {rating or 'n/a'} | Stores: {stores}")
        else:
            print("    [warn] RAWG: no match found")
    else:
        print("[I/IX] RAWG API key not configured — skipping")

    # ── Assemble layers
    print("\n[provenance] Assembling layers...")
    layers = []
    layers.append(build_layer_identity(title, platform, region, igdb_game, moby_game, rawg_data=rawg_data))
    layers.append(build_layer_origin(igdb_comps, igdb_game, wiki_data))
    if announcement_date:
        layers[-1]["announcement_date_proxy"] = announcement_date
    layers.append(build_layer_human(moby_credits_data, wiki_ib=wiki_ib))
    layers.append(build_layer_music(title, moby_credits_data, wiki_ib=wiki_ib))
    layers.append(build_layer_screenshots(screenshots))
    layers.append(build_layer_context(title, platform, region, wiki_ib))
    layers.append(build_layer_market(title, platform, region, wiki_ib, ebay_data))
    layers.append(build_layer_discovery(igdb_similar))
    layers.append(build_layer_survival(title, platform, rawg_data=rawg_data))
    layers.append(build_layer_verdict(title, platform, region, layers))

    result = {
        "provenance_version": "0.2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query": {"title": title, "platform": platform, "region": region},
        "layers": layers,
    }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="provenance.py — Forensic History Generator for Physical Game Objects"
    )
    parser.add_argument("title",    help='Game title, e.g. "7 Sins"')
    parser.add_argument("platform", help="Platform: PC, PS2, PS3, Xbox, Xbox 360, Wii, etc.")
    parser.add_argument("--region", default="EUR", help="Region: EUR, USA, JAP (default: EUR)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                        help="Path to JSON config with API keys")
    parser.add_argument("--out",    default=None,
                        help="Output JSON path (default: {title}_{platform}_provenance.json)")
    args = parser.parse_args()

    config = load_config(Path(args.config))

    result = run_provenance(args.title, args.platform, args.region, config)

    # Output path
    out_path = args.out or f"{slugify(args.title)}_{slugify(args.platform)}_provenance.json"
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n[provenance] ✓ Written to {out_path}")

    # Quick summary to stdout
    print("\n── LAYER SUMMARY ──────────────────────────────────")
    for layer in result["layers"]:
        print(f"  {layer.get('layer', '?')}")
    print("────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
