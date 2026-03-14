#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Lord of the Files — Scan Pipeline Setup
# Run this once before first use: bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

VENV_DIR="venv"
PYTHON_MIN="3.9"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║       LORD OF THE FILES — SCAN PIPELINE SETUP       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Check Python version ──────────────────────────────────────────────────
echo "[1/6] Checking Python version..."

if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo ""
    echo "  ✗ Python not found."
    echo "  Install it with:"
    echo "    Ubuntu/Debian:  sudo apt install python3"
    echo "    Arch:           sudo pacman -S python"
    echo "    Fedora:         sudo dnf install python3"
    echo ""
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo ""
    echo "  ✗ Python $PYTHON_VERSION found but $PYTHON_MIN or higher is required."
    echo "  Please update Python and run setup again."
    echo ""
    exit 1
fi

echo "  ✓ Python $PYTHON_VERSION found"

# ── 2. Check system dependencies ─────────────────────────────────────────────
echo ""
echo "[2/6] Checking system dependencies..."

MISSING_DEPS=()

# Tesseract OCR
if command -v tesseract &>/dev/null; then
    TESS_VERSION=$(tesseract --version 2>&1 | head -1)
    echo "  ✓ Tesseract found: $TESS_VERSION"
else
    echo "  ✗ Tesseract NOT found"
    MISSING_DEPS+=("tesseract")
fi

# libzbar (for barcode scanning)
if ldconfig -p 2>/dev/null | grep -q "libzbar" || \
   [ -f "/usr/lib/libzbar.so" ] || \
   [ -f "/usr/lib/x86_64-linux-gnu/libzbar.so.0" ] || \
   [ -f "/usr/local/lib/libzbar.so" ]; then
    echo "  ✓ libzbar found"
else
    echo "  ✗ libzbar NOT found"
    MISSING_DEPS+=("libzbar")
fi

# If missing deps — print install instructions and exit
if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo ""
    echo "  ─────────────────────────────────────────────────────"
    echo "  Some required system packages are missing."
    echo "  Run the following command and then run setup.sh again:"
    echo ""

    # Detect distro
    if command -v apt &>/dev/null; then
        INSTALL_CMD="sudo apt install"
        PKG_TESS="tesseract-ocr"
        PKG_ZBAR="libzbar0"
    elif command -v pacman &>/dev/null; then
        INSTALL_CMD="sudo pacman -S"
        PKG_TESS="tesseract"
        PKG_ZBAR="zbar"
    elif command -v dnf &>/dev/null; then
        INSTALL_CMD="sudo dnf install"
        PKG_TESS="tesseract"
        PKG_ZBAR="zbar"
    else
        INSTALL_CMD="[your package manager] install"
        PKG_TESS="tesseract"
        PKG_ZBAR="zbar"
    fi

    PKGS=""
    for dep in "${MISSING_DEPS[@]}"; do
        if [ "$dep" = "tesseract" ]; then PKGS="$PKGS $PKG_TESS"; fi
        if [ "$dep" = "libzbar" ]; then PKGS="$PKGS $PKG_ZBAR"; fi
    done

    echo "    $INSTALL_CMD$PKGS"
    echo ""
    echo "  ─────────────────────────────────────────────────────"
    exit 1
fi

# ── 3. Create virtual environment ────────────────────────────────────────────
echo ""
echo "[3/6] Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo "  ✓ venv already exists — skipping creation"
else
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "  ✓ venv created at ./$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# ── 4. Install Python dependencies ───────────────────────────────────────────
echo ""
echo "[4/6] Installing Python packages (this may take a minute)..."

pip install --upgrade pip --quiet

PACKAGES=(
    "opencv-python"
    "Pillow"
    "pytesseract"
    "pyzbar"
    "piexif"
    "requests"
    "tqdm"
    "howlongtobeatpy"
)

for pkg in "${PACKAGES[@]}"; do
    echo -n "  Installing $pkg... "
    pip install "$pkg" --quiet
    echo "✓"
done

# ── 5. Create keys config if missing ─────────────────────────────────────────
echo ""
echo "[5/6] Checking API keys config..."

if [ -f "provenance_keys.json" ]; then
    echo "  ✓ provenance_keys.json already exists"
else
    cat > provenance_keys.json << 'EOF'
{
  "igdb_client_id": "",
  "igdb_client_secret": "",
  "mobygames_api_key": "",
  "youtube_api_key": "",
  "ebay_app_id": "",
  "ebay_cert_id": ""
}
EOF
    echo "  ✓ provenance_keys.json created — fill in your API keys"
fi

# ── 6. Create run.sh launcher ────────────────────────────────────────────────
echo ""
echo "[6/6] Creating launcher scripts..."

cat > run_scan.sh << 'EOF'
#!/bin/bash
# Launcher for scan.py — activates venv automatically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/scan.py" "$@"
EOF
chmod +x run_scan.sh

cat > run_provenance.sh << 'EOF'
#!/bin/bash
# Launcher for provenance.py — activates venv automatically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/provenance.py" "$@"
EOF
chmod +x run_provenance.sh

echo "  ✓ run_scan.sh created"
echo "  ✓ run_provenance.sh created"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║                  SETUP COMPLETE ✓                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Next steps:"
echo "  1. Fill in API keys in provenance_keys.json"
echo "  2. To scan a photo:     ./run_scan.sh --photo your_photo.jpg --platform PS2"
echo "  3. To run provenance:   ./run_provenance.sh \"Game Title\" PC"
echo ""
echo "  Photo guide: docs/PHOTO_GUIDE.md"
echo ""
