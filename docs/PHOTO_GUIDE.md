# Photo Guide — Scanning Physical Game Collections

This guide covers how to photograph game spines and backs for reliable code extraction with `scan.py`.

---

## General principles

- **Optical resolution is the hard limit.** Sharpening in post does not recover detail that wasn't captured. Get close, get parallel, get sharp at capture time.
- **White card behind spines is mandatory** — especially for dark cases (PS2 Platinum, PS3 black). Without contrast background, OCR fails.
- **Max 8–12 spines per frame** for PS2/PS3. More than that = codes too small to read reliably.

---

## PS2 — White label (standard)

```
Setup:   wooden strip with double-sided tape on desk, games upright and tight
Card:    white A4 sheet behind the row
Light:   daylight from side, or angled desk lamp — avoid direct overhead flash
Per frame: max 12 spines
Phone:   close and parallel to shelf, macro mode on, any orientation (EXIF handles rotation)
```

**Ambiguous digit pairs at low resolution:**

| Pair | Looks like |
|------|-----------|
| 1 / 7 | Most common misread |
| 3 / 8 | Common |
| 0 / 6 | Common |
| 4 / 9 | Less common |
| 5 / 6 | Less common |

The script flags these as `status: flagged` for manual verification.

---

## PS2 — Platinum (black cases)

Same as white label but:
- White card is **mandatory**, not optional
- Shoot as a **separate batch** from white label
- Use `--dark` flag: `./run_scan.sh --photo batch_platinum.jpg --platform PS2 --dark`

The `--dark` flag inverts the threshold before OCR, which recovers text on dark backgrounds.

---

## PS3

Same protocol as PS2. Separate batch from PS2 (different code prefix: BLES/BCES).

---

## Xbox / Xbox 360

Photograph spines for title OCR. Microsoft product codes on back (U19-00039, C8K-00006) are **not useful** — no public database. Script uses title from OCR → IGDB title search.

---

## PC

Photograph the **back cover**, flat on a surface, from directly above. EAN-13 barcode is the primary identifier. Spine codes on PC games (G10-00027, U28-00013 etc.) are decorative — ignore.

```
Setup:   back cover flat on table
Light:   even, no shadows over barcode
Phone:   directly above, perpendicular to surface
```

---

## Physical setup recommendation

Wooden strips (shelf dividers or offcuts) with double-sided tape on your desk. Games slot in tight and stay vertical without holding them. Leaves both hands free for the phone.

---

## What the script checks before OCR

```
Minimum resolution:  800 × 800 px
Brightness:          mean pixel value 30–240 (rejects too dark / overexposed)
Blur:                Laplacian variance > 50 (rejects out-of-focus shots)
```

If your image fails any check, the script prints exactly why and what to fix. Retake the photo — don't try to fix it in software.

---

## Manual entry cases

Some items cannot be identified automatically:

| Item type | Reason | Action |
|-----------|--------|--------|
| NOT FOR RESALE copies | No EAN on bundle copies | Manual title entry |
| Magazine covermount discs | No standard barcode | Manual entry |
| Pressing plant codes (VTV BELGIUM...) | Not a lookup key | Manual entry |
| Disc ring / mastering codes | Not in public API | Skip or note |
| Sega product codes (MK-XXXXX) | No unified DB | Manual entry |

These appear in `scan_issues.txt` with `status: manual_required`.
