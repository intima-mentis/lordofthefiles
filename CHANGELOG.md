# Changelog

All notable changes to this project are documented here.

---

## [0.1.0] — 2026-03-14

### Added
- `provenance.py` — 10-layer forensic history generator for physical game objects
- `scan.py` — photo pipeline for spine code OCR and EAN barcode scanning
- `setup.sh` — venv-based installer with system dependency detection (Tesseract, libzbar)
- `run_provenance.sh` / `run_scan.sh` — launcher scripts with auto venv activation
- `provenance_keys.json.template` — safe public template for API key configuration
- `docs/PHOTO_GUIDE.md` — photography protocol for reliable code extraction

### Provenance layers (v0.1.0)
- **Layer I · Identity** — IGDB + MobyGames, release date, DB cross-references
- **Layer II · Origin** — IGDB companies, Wikipedia summary
- **Layer III · Human** — Wikipedia infobox fallback (MobyGames credits API confirmed non-functional)
- **Layer IV · Music** — Composer attribution, VGMdb + khinsider search links
- **Layer V · Screenshots** — MobyGames API, up to 6 per game
- **Layer VI · Context** — Wikipedia regional/censorship section detection
- **Layer VII · Market** — Wikipedia sales data (infobox + narrative parser), eBay structure ready
- **Layer VIII · Discovery** — IGDB similar_games field
- **Layer IX · Survival** — GOG/Steam/ProtonDB search links
- **Layer X · Verdict** — Forensic summary placeholder for manual annotation

### Known issues (alpha)
- MobyGames credits endpoint returns 0 results — confirmed API limitation
- eBay live pricing requires separate Browse API approval (pending)
- Layer IX links generated but not auto-verified
- RAWG and OpenLibrary integrations not yet added

### Tested on
- PS2 PAL: Trapt, Mafia, GTA San Andreas, GTA Vice City
- PS3 PAL: Call of Duty Black Ops, Assassin's Creed Brotherhood
- PC EUR: 7 Sins, Halo 2

---

## [0.2.0] — 2026-03-14

### Added
- RAWG API integration — `rawg_find_game()` + `rawg_extract()` functions
- `rawg_id` added to all entries in `PLATFORM_MAP`
- **Layer I** now includes: `metacritic_score`, `metacritic_score_platform`, `metacritic_url`, `rawg_rating`, `rawg_ratings_count`, `playtime_hours_avg`, `tags`, `genres`, `rawg_id`, `rawg_url`
- **Layer IX** now uses verified store links from RAWG (`stores_verified`) when available, replacing generated search URLs
- `rawg_api_key` added to `CONFIG_TEMPLATE` and `provenance_keys.json.template`
- `RAWG_STORE_NAMES` lookup table (Steam, GOG, PlayStation Store, Epic, itch.io etc.)
- Platform fallback search (retries without platform filter if no results)
- Exact title match preference in RAWG results

### Changed
- `build_layer_identity()` accepts optional `rawg_data` parameter
- `build_layer_survival()` accepts optional `rawg_data` parameter — upgrades from search links to verified store URLs when RAWG data is present

## [0.3.0] — 2026-03-14

### Added
- HowLongToBeat integration — `hltb_times()` function using `howlongtobeatpy`
- **Layer I** now includes: `hltb_main_story_hours`, `hltb_main_extra_hours`, `hltb_completionist_hours`, `hltb_url`
- Similarity threshold (0.6) — rejects weak HLTB matches to avoid wrong game data
- Graceful degradation — HLTB skipped silently if `howlongtobeatpy` not installed
- `howlongtobeatpy` added to `setup.sh` package list

### Fixed
- `wiki_summary()` now tries `"{title} (video game)"` first before plain title — fixes wrong Wikipedia page for ambiguous titles like "Mafia"
- Added game page detection via keyword check on description/extract as secondary guard

## [0.3.1] — 2026-03-14

### Fixed
- Wikidata credits call was dead code inside `wiki_infobox()` — moved to top-level `run_provenance()` as a proper pipeline stage
- Wikidata now fires correctly when infobox director/composer are missing
- ICO: Fumito Ueda (director) + Michiru Oshima, Koichi Yamazaki (composer) now resolved via Wikidata P57/P86
- Source label `"Wikipedia infobox (designer field)"` added when director falls back to designer field

## [Unreleased]

### Planned
- RAWG API integration (Metacritic scores, tags)
- OpenLibrary / Open EAN barcode lookup for PC
- `watermark.py` — EXIF embed + export watermarking
- eBay live pricing (pending API key)
- HTML condition checker (mobile-first, offline, exportable)
