# Intima Mentis
### Physical Media Forensics Toolkit

> **Status: Alpha** — core pipeline functional, API integrations tested, active development.  
> Part of the [Lord of the Files](https://refucktory.world) project — a forensic cataloguing practice for physical game collections.

---

Physical games are dying a quiet death. Not the objects themselves — discs and cases outlast servers — but the *context* around them. Who made it. Who scored it. How many were pressed. Whether the PAL version was cut. Whether anyone ever digitized the soundtrack.

**Intima Mentis** is a toolkit for generating structured forensic provenance records for physical game objects. You give it a title, platform, and region. It assembles everything publicly known about that object into a layered JSON document — identity, origin, human attribution, music, regional context, market data, survival status.

The goal is not a database. It's a methodology.

---

## What it does

```
python provenance.py "Mafia" PS2 --region EUR
```

Generates a 10-layer provenance record:

| Layer | What it captures | Source |
|-------|-----------------|--------|
| I · Identity | Title, platform, release date, DB IDs | IGDB + MobyGames |
| II · Origin | Developer, publisher, Wikipedia summary | IGDB + Wikipedia |
| III · Human | Director, composer, key credits | Wikipedia infobox |
| IV · Music | Composer, OST status, search links | Wikipedia + VGMdb |
| V · Screenshots | Visual evidence of the object | MobyGames API |
| VI · Context | Regional cuts, censorship flags | Wikipedia wikitext |
| VII · Market | Units sold, eBay active listings | Wikipedia + eBay |
| VIII · Discovery | Similar titles (algorithmic) | IGDB |
| IX · Survival | GOG/Steam/ProtonDB availability | Links generated |
| X · Verdict | Forensic summary, keep/sell/document | Manual completion |

---

## scan.py — Photo Pipeline

```
./run_scan.sh --photo spines.jpg --platform PS2
./run_scan.sh --batch ./photos/ --platform PC
./run_scan.sh --resume
```

Reads physical game spine photos and extracts product codes (SLES/BLES etc.) or EAN barcodes:

- Auto-rotation via EXIF (`exif_transpose`) — any phone angle accepted
- Image quality validation before OCR (brightness, blur, minimum resolution)
- Tesseract OCR with 4-rotation pass for spine codes
- pyzbar barcode scanning with 3 image versions for reliability
- `--dark` flag for PS2 Platinum / PS3 black cases
- `--resume` to recover interrupted batch sessions
- Clean progress bars (tqdm) + issue log output

---

## Platforms supported

| Platform | Primary ID | Method |
|----------|-----------|--------|
| PS2 PAL | SLES/SCES (spine) | OCR |
| PS3 PAL | BLES/BCES (spine) | OCR |
| Xbox / Xbox 360 | Title (spine) | OCR → IGDB title search |
| PC | EAN-13 barcode (back) | pyzbar → Open EAN lookup |
| PS1 PAL | SLES/SCES (spine) | OCR |
| Wii | RVL code | OCR |
| Dreamcast | T-code | OCR |

---

## Installation

```bash
# Clone the repo
git clone https://github.com/intima-mentis/lordofthefiles.git
cd intima-mentis

# Run setup (creates venv, checks system deps, installs packages)
bash setup.sh
```

**System requirements:**
- Python 3.9+
- Tesseract OCR (`sudo apt install tesseract-ocr`)
- libzbar (`sudo apt install libzbar0`)

Setup script auto-detects distro and prints the exact install command if anything is missing.

---

## API Keys

Copy `provenance_keys.json.template` to `provenance_keys.json` and fill in your keys:

```json
{
  "igdb_client_id": "",
  "igdb_client_secret": "",
  "mobygames_api_key": "",
  "youtube_api_key": "",
  "ebay_app_id": ""
}
```

| Key | Where to get it | Required |
|-----|----------------|----------|
| IGDB | [dev.twitch.tv/console/apps](https://dev.twitch.tv/console/apps) | Yes |
| MobyGames | [mobygames.com/info/api](https://www.mobygames.com/info/api/) | Yes |
| YouTube | Google Cloud Console — YouTube Data API v3 | Optional |
| eBay | [developer.ebay.com](https://developer.ebay.com) Browse API | Optional |

`provenance_keys.json` is in `.gitignore` — never committed.

---

## Example output

See [`examples/provenance_output/`](examples/provenance_output/) for real outputs from alpha testing:

- `Trapt_PS2_EUR.json` — rare PAL release, composer unattributed
- `Mafia_PS2_EUR.json` — Illusion Softworks, 2M units sold (Wikipedia)
- `Halo_2_PC_EUR.json` — Martin O'Donnell confirmed via Wikipedia infobox
- `Call_of_Duty__Black_Ops_PS3_EUR.json` — standard edition preference logic tested
- `Assassins_Creed_Brotherhood_PS3_EUR.json` — Jesper Kyd confirmed

---

## Known limitations (alpha)

- **MobyGames credits API** — endpoint exists but returns 0 results for all games (confirmed API limitation, website-only). Wikipedia infobox is the working fallback.
- **eBay Layer VII** — requires eBay Browse API approval (separate from app registration). Live pricing pending.
- **Layer IX survival** — GOG/Steam links generated but not auto-verified. Manual check required.
- **Layer X verdict** — structural placeholder. Intended for manual forensic annotation.
- **RAWG integration** — Metacritic scores and tags not yet added (planned next).
- **OpenLibrary/Open EAN** — PC EAN lookup not yet integrated (planned next).

---

## Roadmap

- [ ] RAWG API — Metacritic score, tags, user ratings (Layer I/VIII enrichment)
- [ ] OpenLibrary / Open EAN — PC barcode → title resolution
- [ ] `watermark.py` — EXIF embed + transparent watermark on export photos
- [ ] `docs/PHOTO_GUIDE.md` — full photo setup reference with annotated examples
- [ ] eBay live pricing — pending API approval
- [ ] HTML condition checker — mobile-first, offline-capable, exportable

---

## Project context

This toolkit is part of a broader forensic cataloguing practice — [Lord of the Files](https://refucktory.world) — focused on physical media preservation, digital archiving methodology, and building a public portfolio in digital forensics.

The name *Intima Mentis* (inner mind / innermost record) refers to the idea that every physical object carries more history than its surface shows. The tools here try to surface that history in a structured, reproducible way.

---

## License

MIT

---

*Built by [Charlie Header](https://refucktory.world) · Dubiecko, Poland · 2026*
