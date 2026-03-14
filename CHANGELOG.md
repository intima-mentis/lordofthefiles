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

## [Unreleased]

### Planned
- RAWG API integration (Metacritic scores, tags)
- OpenLibrary / Open EAN barcode lookup for PC
- `watermark.py` — EXIF embed + export watermarking
- eBay live pricing (pending API key)
- HTML condition checker (mobile-first, offline, exportable)
