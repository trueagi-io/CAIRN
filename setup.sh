#!/bin/bash
# CAIRN setup script
# Verifies sibling repos, checks PeTTa/Janus, and installs Python deps
#
# Usage:
#   bash setup.sh            # first-time setup
#   bash setup.sh --rebuild  # recreate an existing venv

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_ENV_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== CAIRN Setup ==="
echo "Checking prerequisites..."

# Verify sibling repos
for repo in PeTTa metta-attention hyperon-experimental; do
    if [ ! -d "$DEV_ENV_DIR/$repo" ]; then
        echo "❌ Missing sibling repo: $DEV_ENV_DIR/$repo"
        echo "   Clone all required repos as siblings in MeTTa-dev-env/"
        exit 1
    fi
    echo "✓ Found $repo"
done

# Verify PeTTa is runnable
if [ ! -f "$DEV_ENV_DIR/PeTTa/run.sh" ]; then
    echo "❌ PeTTa/run.sh not found"
    exit 1
fi
echo "✓ PeTTa/run.sh found"

# Verify PeTTa lib_import (provides static-import! for knowledge graph loading)
if [ ! -f "$DEV_ENV_DIR/PeTTa/lib/lib_import.pl" ]; then
    echo "❌ PeTTa/lib/lib_import.pl not found (needed for static-import!)"
    exit 1
fi
echo "✓ PeTTa lib_import found"

# Verify swipl is installed
if ! command -v swipl &>/dev/null; then
    echo "❌ swipl not found. Install SWI-Prolog ≥ 9.3 (see ../PeTTa/README.md)"
    exit 1
fi
echo "✓ swipl found ($(swipl --version 2>&1 | head -1))"

# Detect which Python version SWI-Prolog's Janus is linked against.
# The venv MUST use this exact version — compiled extensions are ABI-specific.
echo ""
echo "Detecting Janus Python version..."
JANUS_PY_VER=$(swipl -q -g \
  "use_module(library(janus)),
   py_call(sys:version_info, V),
   V = -(Ma, Mi, _, _, _),
   format('~w.~w', [Ma, Mi]),
   halt" 2>/dev/null) || true

if [ -z "$JANUS_PY_VER" ]; then
    echo "❌ Could not detect Janus Python version."
    echo "   Ensure SWI-Prolog was built with Janus (Python) support."
    exit 1
fi
echo "✓ Janus uses Python $JANUS_PY_VER"

# Find a system Python interpreter matching Janus
PYTHON_BIN=""
for candidate in "python${JANUS_PY_VER}" "python3" "/usr/bin/python3" "/usr/bin/python${JANUS_PY_VER}"; do
    if command -v "$candidate" &>/dev/null || [ -x "$candidate" ]; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>/dev/null) || continue
        if [ "$ver" = "$JANUS_PY_VER" ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Janus requires Python $JANUS_PY_VER but no matching interpreter found on this system."
    echo "   Install Python $JANUS_PY_VER or rebuild SWI-Prolog against your installed Python."
    exit 1
fi
echo "✓ Using interpreter: $PYTHON_BIN"

# Check metta-attention experiment data
echo ""
echo "Checking experiment data..."
KG_QLF="$DEV_ENV_DIR/metta-attention/experiments/data/kg.qlf"
KG_METTA="$DEV_ENV_DIR/metta-attention/experiments/data/kg.metta"
if [ -f "$KG_QLF" ]; then
    echo "✓ Pre-compiled knowledge graph found (kg.qlf)"
elif [ -f "$KG_METTA" ]; then
    echo "⚠ kg.qlf not found — first demo run will compile kg.metta (may be slow)"
else
    echo "⚠ Knowledge graph not found — demo will not be able to load experiment data"
fi

# Create virtual environment
echo ""
echo "Setting up Python virtual environment..."
if [ -d "$SCRIPT_DIR/venv" ]; then
    if [ "$1" = "--rebuild" ]; then
        echo "  Removing existing venv (--rebuild)..."
        rm -rf "$SCRIPT_DIR/venv"
    else
        echo "❌ venv/ already exists. Run 'bash setup.sh --rebuild' to recreate it."
        exit 1
    fi
fi

"$PYTHON_BIN" -m venv "$SCRIPT_DIR/venv"
source "$SCRIPT_DIR/venv/bin/activate"
echo "✓ Virtual environment created (Python $JANUS_PY_VER)"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -q -r "$SCRIPT_DIR/requirements.txt"
echo "✓ Dependencies installed"

echo ""
echo "=== Setup Complete ==="
echo "To use CAIRN in future shells:"
echo "  source venv/bin/activate"
echo ""
echo "Run the demo:"
echo "  ../PeTTa/run.sh demo.metta"
