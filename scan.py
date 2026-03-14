#!/usr/bin/env python3
"""
scan.py — Photo Pipeline for Game Code Recognition
Lord of the Files | Extracted Minds Lab

Usage:
  ./run_scan.sh --photo spines.jpg --platform PS2
  ./run_scan.sh --photo backs.jpg --platform PC
  ./run_scan.sh --batch ./photos/ --platform PS3
  ./run_scan.sh --resume

Output: scan_results.json + scan_issues.txt
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Dependency check (friendly errors before any import crash) ───────────────
def check_dependencies():
    missing = []
    try:
        import cv2
    except ImportError:
        missing.append("opencv-python")
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")
    try:
        import pytesseract
    except ImportError:
        missing.append("pytesseract")
    try:
        from pyzbar import pyzbar
    except ImportError:
        missing.append("pyzbar")
    try:
        from tqdm import tqdm
    except ImportError:
        missing.append("tqdm")

    if missing:
        print("")
        print("  ✗ Missing Python packages:", ", ".join(missing))
        print("  Did you run setup.sh first?")
        print("  Run:  bash setup.sh")
        print("")
        sys.exit(1)

check_dependencies()

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps
from pyzbar import pyzbar
from tqdm import tqdm

# ── Check Tesseract binary ────────────────────────────────────────────────────
def check_tesseract():
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        print("")
        print("  ✗ Tesseract OCR not found on your system.")
        print("  Install it with:")
        print("    Ubuntu/Debian:  sudo apt install tesseract-ocr")
        print("    Arch:           sudo pacman -S tesseract")
        print("    Fedora:         sudo dnf install tesseract")
        print("")
        sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────

SESSION_FILE = Path("scan_session.json")
RESULTS_FILE = Path("scan_results.json")
ISSUES_FILE  = Path("scan_issues.txt")

PLATFORM_CODE_PATTERNS = {
    "PS2":      [r"SL[EUA][SCDP]-\d{5}(?:[/\w]*)?"],
    "PS3":      [r"B[LC][EUA][SCDP]-?\d{5}(?:[/\w]*)?"],
    "Xbox":     [r"[A-Z0-9]{2,4}-\d{5}"],
    "Xbox 360": [r"[A-Z0-9]{2,4}-\d{5}"],
    "PC":       [],  # EAN barcode only
    "Wii":      [r"RVL-[A-Z0-9]{4}-[A-Z0-9]{3}"],
    "Dreamcast":[r"T-\d{5}[A-Z]?"],
    "PS1":      [r"SL[EUA][SCDP]-\d{5}(?:[/\w]*)?"],
}

PLATFORM_SPINE_CODES = ["PS2", "PS3", "Xbox", "Xbox 360", "PS1", "Wii", "Dreamcast"]
PLATFORM_BARCODE     = ["PC"]

# ── Progress display ──────────────────────────────────────────────────────────

def spinner_msg(msg: str):
    """Print a status message with timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")


def print_header():
    print("")
    print("╔══════════════════════════════════════════════════════╗")
    print("║         LORD OF THE FILES — SCAN PIPELINE           ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("")


def print_batch_summary(results: list):
    total     = len(results)
    success   = sum(1 for r in results if r["status"] == "ok")
    flagged   = sum(1 for r in results if r["status"] == "flagged")
    failed    = sum(1 for r in results if r["status"] == "failed")
    manual    = sum(1 for r in results if r["status"] == "manual_required")

    print("")
    print("╔══════════════════════════════════════════════════════╗")
    print(f"║  BATCH COMPLETE — {total} items processed{' ' * (23 - len(str(total)))}║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  ✓  {success} resolved successfully{' ' * (35 - len(str(success)))}║")
    if flagged:
        print(f"║  ⚠  {flagged} flagged — need manual input{' ' * (29 - len(str(flagged)))}║")
    if failed:
        print(f"║  ✗  {failed} failed — retake photo{' ' * (32 - len(str(failed)))}║")
    if manual:
        print(f"║  ✎  {manual} manual entry required{' ' * (31 - len(str(manual)))}║")
    print("╚══════════════════════════════════════════════════════╝")

    if flagged or failed or manual:
        print(f"\n  Problem list saved to: {ISSUES_FILE}")


# ── Image preprocessing ───────────────────────────────────────────────────────

def load_and_orient(image_path: str) -> np.ndarray:
    """Load image and auto-rotate based on EXIF orientation."""
    spinner_msg(f"Loading image: {Path(image_path).name}")
    try:
        pil_img = Image.open(image_path)
        pil_img = ImageOps.exif_transpose(pil_img)  # auto-rotate from EXIF
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        spinner_msg(f"  Image size: {img.shape[1]}x{img.shape[0]}px")
        return img
    except Exception as e:
        print(f"  ✗ Could not load image: {e}")
        return None


def validate_image(img: np.ndarray) -> tuple[bool, str]:
    """
    Basic quality checks before processing.
    Returns (passed, reason_if_failed).
    """
    if img is None:
        return False, "Could not load image file"

    h, w = img.shape[:2]

    # Too small
    if w < 800 or h < 800:
        return False, f"Image too small ({w}x{h}px). Minimum 800x800px. Retake photo."

    # Check brightness
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)

    if mean_brightness < 30:
        return False, "Image too dark. Move closer to window or add more light."
    if mean_brightness > 240:
        return False, "Image overexposed. Avoid direct flash or bright sunlight on cases."

    # Check blur
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 50:
        return False, "Image too blurry. Hold phone steady, use macro mode if available."

    return True, "ok"


def preprocess_for_ocr(img: np.ndarray, dark_boxes: bool = False) -> np.ndarray:
    """
    Adaptive preprocessing for OCR.
    dark_boxes=True for black PS2 Platinum cases.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # CLAHE — adaptive contrast (works in low light)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Bilateral filter — removes noise, keeps edges
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)

    # Threshold
    if dark_boxes:
        # For dark backgrounds — invert before threshold
        inverted = cv2.bitwise_not(denoised)
        _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresh


def preprocess_for_barcode(img: np.ndarray) -> np.ndarray:
    """Preprocessing optimized for barcode detection."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return enhanced


# ── Barcode scanning ──────────────────────────────────────────────────────────

def scan_barcodes(img: np.ndarray) -> list[dict]:
    """
    Scan image for EAN-13 and other barcodes.
    Tries multiple preprocessed versions for best results.
    """
    spinner_msg("Scanning for barcodes...")
    found = []
    seen_data = set()

    versions = [
        img,
        preprocess_for_barcode(img),
    ]

    # Also try upscaled version if image is small
    h, w = img.shape[:2]
    if w < 2000:
        scale = 2000 / w
        upscaled = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        versions.append(upscaled)

    for version in versions:
        # pyzbar needs PIL
        if len(version.shape) == 2:
            pil = Image.fromarray(version)
        else:
            pil = Image.fromarray(cv2.cvtColor(version, cv2.COLOR_BGR2RGB))

        barcodes = pyzbar.decode(pil)
        for bc in barcodes:
            data = bc.data.decode("utf-8", errors="replace").strip()
            if data and data not in seen_data:
                seen_data.add(data)
                found.append({
                    "type": bc.type,
                    "data": data,
                    "rect": {
                        "x": bc.rect.left,
                        "y": bc.rect.top,
                        "w": bc.rect.width,
                        "h": bc.rect.height,
                    }
                })

    if found:
        spinner_msg(f"  ✓ Found {len(found)} barcode(s)")
        for bc in found:
            spinner_msg(f"    {bc['type']}: {bc['data']}")
    else:
        spinner_msg("  — No barcodes found in this image")

    return found


# ── OCR for spine codes ───────────────────────────────────────────────────────

def extract_spine_codes(img: np.ndarray, platform: str, dark_boxes: bool = False) -> list[dict]:
    """
    OCR the image to find SLES/BLES/etc. codes.
    Tries both normal and 90° rotated versions.
    """
    spinner_msg(f"Running OCR for {platform} spine codes...")

    patterns = PLATFORM_CODE_PATTERNS.get(platform, [])
    if not patterns:
        spinner_msg("  — No spine code pattern defined for this platform")
        return []

    found = []
    seen = set()

    # Try normal + rotated versions
    rotations = [0, 90, 270, 180]

    with tqdm(rotations, desc="  OCR rotations", unit="rot",
              bar_format="  {l_bar}{bar}| {n_fmt}/{total_fmt}", leave=False) as pbar:

        for angle in pbar:
            if angle == 0:
                rotated = img.copy()
            else:
                h, w = img.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(img, M, (w, h))

            preprocessed = preprocess_for_ocr(rotated, dark_boxes=dark_boxes)
            pil = Image.fromarray(preprocessed)

            # OCR config: assume sparse text, OSD
            config = "--oem 3 --psm 11"
            try:
                text = pytesseract.image_to_string(pil, config=config)
            except Exception as e:
                spinner_msg(f"  ⚠ OCR error at {angle}°: {e}")
                continue

            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    clean = match.strip().upper()
                    if clean not in seen:
                        seen.add(clean)
                        found.append({
                            "code": clean,
                            "rotation_found": angle,
                            "platform": platform,
                        })
                        spinner_msg(f"    ✓ Found: {clean} (at {angle}°)")

    if not found:
        spinner_msg("  — No spine codes found via OCR")

    return found


# ── Code validation ───────────────────────────────────────────────────────────

def validate_ean13(code: str) -> bool:
    """Validate EAN-13 checksum."""
    digits = re.sub(r"\D", "", code)
    if len(digits) != 13:
        return False
    total = sum(
        int(d) * (1 if i % 2 == 0 else 3)
        for i, d in enumerate(digits[:12])
    )
    check = (10 - (total % 10)) % 10
    return check == int(digits[12])


def classify_code(code: str, platform: str) -> dict:
    """Classify what kind of code this is."""
    clean = code.strip().upper().replace(" ", "").replace("-", "")

    # EAN-13
    digits_only = re.sub(r"\D", "", code)
    if len(digits_only) == 13:
        valid = validate_ean13(code)
        return {
            "code": code,
            "type": "barcode_ean13",
            "valid_checksum": valid,
            "lookup_ready": valid,
        }

    # SLES/SCES/SLUS etc.
    if re.match(r"SL[EUA][SCDP]-?\d{5}", clean):
        return {"code": code, "type": "product_code_ps", "lookup_ready": True}

    # BLES/BCES etc.
    if re.match(r"B[LC][EUA][SCDP]-?\d{5}", clean):
        return {"code": code, "type": "product_code_ps3", "lookup_ready": True}

    return {"code": code, "type": "unknown", "lookup_ready": False}


# ── Single image processor ────────────────────────────────────────────────────

def process_image(image_path: str, platform: str,
                  dark_boxes: bool = False, batch_index: int = None,
                  batch_total: int = None) -> dict:
    """
    Full pipeline for one image.
    Returns a result dict with status, codes found, and any issues.
    """
    prefix = f"[{batch_index}/{batch_total}] " if batch_index else ""
    print(f"\n{prefix}Processing: {Path(image_path).name}")
    print("  " + "─" * 50)

    result = {
        "image": str(image_path),
        "platform": platform,
        "processed_at": datetime.utcnow().isoformat(),
        "status": "failed",
        "codes": [],
        "barcodes": [],
        "issues": [],
        "manual_required": False,
        "sealed": None,
    }

    # Load + orient
    img = load_and_orient(image_path)
    if img is None:
        result["issues"].append("Could not load image file")
        result["status"] = "failed"
        return result

    # Validate
    spinner_msg("Validating image quality...")
    passed, reason = validate_image(img)
    if not passed:
        print(f"  ✗ Image validation failed: {reason}")
        result["issues"].append(reason)
        result["status"] = "failed"
        return result
    spinner_msg("  ✓ Image quality OK")

    # Branch: barcode platform or spine code platform
    if platform in PLATFORM_BARCODE:
        barcodes = scan_barcodes(img)
        for bc in barcodes:
            classified = classify_code(bc["data"], platform)
            result["barcodes"].append({**bc, **classified})

        if not barcodes:
            result["issues"].append(
                "No barcode found. Check: is barcode in frame? Is photo sharp? "
                "Is barcode corner visible (not folded or covered by sticker)?"
            )
            result["manual_required"] = True
            result["status"] = "manual_required"
        else:
            invalid = [b for b in result["barcodes"] if not b.get("valid_checksum", True)]
            if invalid:
                result["issues"].append(
                    f"{len(invalid)} barcode(s) failed checksum validation — "
                    "may be misread. Verify manually."
                )
                result["status"] = "flagged"
            else:
                result["status"] = "ok"

    else:
        # Spine code OCR
        codes = extract_spine_codes(img, platform, dark_boxes=dark_boxes)
        result["codes"] = codes

        if not codes:
            result["issues"].append(
                f"No {platform} codes found via OCR. "
                "Check: photo sharp enough? Codes in frame? "
                "Try closer crop or better lighting."
            )
            result["manual_required"] = True
            result["status"] = "manual_required"
        else:
            result["status"] = "ok"

    # Status summary
    status_icon = {"ok": "✓", "flagged": "⚠", "failed": "✗", "manual_required": "✎"}
    icon = status_icon.get(result["status"], "?")
    spinner_msg(f"{icon} Status: {result['status'].upper()}")

    return result


# ── Batch processor ───────────────────────────────────────────────────────────

def process_batch(photos: list[str], platform: str,
                  dark_boxes: bool = False, resume: bool = False) -> list[dict]:
    """Process multiple images with progress tracking and resume support."""

    results = []
    processed_paths = set()

    # Resume: load existing session
    if resume and SESSION_FILE.exists():
        print("\n  Resuming previous session...")
        session = json.loads(SESSION_FILE.read_text())
        results = session.get("results", [])
        processed_paths = {r["image"] for r in results}
        remaining = [p for p in photos if p not in processed_paths]
        print(f"  Already processed: {len(results)}")
        print(f"  Remaining: {len(remaining)}")
        photos = remaining

    if not photos:
        print("  All images already processed.")
        return results

    total_in_batch = len(photos)
    already_done = len(results)

    print(f"\n  Starting batch: {total_in_batch} image(s) to process")
    print("")

    with tqdm(photos, desc="  Overall progress", unit="photo",
              bar_format="  {l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:

        for i, photo_path in enumerate(pbar, 1):
            global_index = already_done + i
            global_total = already_done + total_in_batch

            pbar.set_postfix_str(Path(photo_path).name[:30])

            result = process_image(
                photo_path, platform,
                dark_boxes=dark_boxes,
                batch_index=global_index,
                batch_total=global_total,
            )
            results.append(result)

            # Save session after each image — so resume works
            SESSION_FILE.write_text(json.dumps({
                "platform": platform,
                "results": results,
                "last_updated": datetime.utcnow().isoformat(),
            }, indent=2, ensure_ascii=False))

    return results


# ── Output writers ────────────────────────────────────────────────────────────

def write_results(results: list[dict]):
    """Write final JSON results and issues text file."""

    # Full JSON
    RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n  Results saved to: {RESULTS_FILE}")

    # Issues file — only problem cases
    issues = [r for r in results if r["status"] != "ok"]
    if issues:
        lines = [
            "LORD OF THE FILES — SCAN ISSUES",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Total problems: {len(issues)}",
            "=" * 50,
            "",
        ]
        for r in issues:
            lines.append(f"FILE:    {r['image']}")
            lines.append(f"STATUS:  {r['status'].upper()}")
            for issue in r.get("issues", []):
                lines.append(f"ISSUE:   {issue}")
            if r.get("manual_required"):
                lines.append("ACTION:  Enter title/code manually")
            lines.append("")

        ISSUES_FILE.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Issues saved to: {ISSUES_FILE}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    check_tesseract()
    print_header()

    parser = argparse.ArgumentParser(
        description="scan.py — Game Code Recognition Pipeline"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--photo",  help="Single photo to process")
    group.add_argument("--batch",  help="Folder of photos to process")
    group.add_argument("--resume", action="store_true",
                       help="Resume interrupted batch from session file")

    parser.add_argument("--platform", required=False,
                        choices=list(PLATFORM_CODE_PATTERNS.keys()),
                        help="Platform: PS2, PS3, PC, Xbox, Xbox 360, etc.")
    parser.add_argument("--dark",  action="store_true",
                        help="Use dark-box preprocessing (PS2 Platinum, PS3 black cases)")

    args = parser.parse_args()

    # Resume doesn't need platform (it's saved in session)
    if args.resume:
        if not SESSION_FILE.exists():
            print("  ✗ No session file found. Nothing to resume.")
            sys.exit(1)
        session = json.loads(SESSION_FILE.read_text())
        platform = session["platform"]
        # Collect all photos from original batch that weren't done
        processed = {r["image"] for r in session["results"]}
        # We need the original file list — stored in session if we add it
        photos = session.get("all_photos", [])
        if not photos:
            print("  ✗ Session file has no photo list. Cannot resume.")
            sys.exit(1)
        results = process_batch(photos, platform, dark_boxes=args.dark, resume=True)

    elif args.photo:
        if not args.platform:
            print("  ✗ --platform is required. Example: --platform PS2")
            sys.exit(1)
        result = process_image(args.photo, args.platform, dark_boxes=args.dark,
                               batch_index=1, batch_total=1)
        results = [result]

    else:  # --batch
        if not args.platform:
            print("  ✗ --platform is required. Example: --platform PC")
            sys.exit(1)
        batch_dir = Path(args.batch)
        if not batch_dir.is_dir():
            print(f"  ✗ Folder not found: {args.batch}")
            sys.exit(1)

        extensions = {".jpg", ".jpeg", ".png", ".webp"}
        photos = sorted([
            str(p) for p in batch_dir.iterdir()
            if p.suffix.lower() in extensions
        ])

        if not photos:
            print(f"  ✗ No image files found in: {args.batch}")
            sys.exit(1)

        print(f"  Found {len(photos)} image(s) in {args.batch}")

        # Save photo list to session for resume support
        SESSION_FILE.write_text(json.dumps({
            "platform": args.platform,
            "all_photos": photos,
            "results": [],
            "started_at": datetime.utcnow().isoformat(),
        }, indent=2))

        results = process_batch(photos, args.platform, dark_boxes=args.dark)

    write_results(results)
    print_batch_summary(results)

    # Clean up session on full success
    all_ok = all(r["status"] == "ok" for r in results)
    if all_ok and SESSION_FILE.exists():
        SESSION_FILE.unlink()
        print("\n  Session file cleaned up (all OK).")


if __name__ == "__main__":
    main()
