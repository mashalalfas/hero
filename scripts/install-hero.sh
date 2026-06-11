#!/bin/bash
# HERO Install Script
# Installs hero CLI from source (development mode)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   HERO Installation                     ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""

# Detect OS
OS="$(uname -s)"
if [[ "$OS" != "Linux" ]]; then
    echo -e "${RED}⚠ Unsupported OS: $OS${NC}"
    echo "  HERO currently supports Linux only."
    exit 1
fi
echo -e "${GREEN}✓${NC} OS: Linux"

# Check for uv
if command -v uv &> /dev/null; then
    UV_AVAILABLE=true
    echo -e "${GREEN}✓${NC} uv found: $(which uv)"
else
    UV_AVAILABLE=false
    echo -e "${YELLOW}⚠ uv not found${NC}"
    echo "  Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  Or: pip install uv"
fi

# Determine install mode
SCRIPT_SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_SOURCE" ]; do
    SCRIPT_SOURCE="$(readlink -f "$SCRIPT_SOURCE")"
done
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_DIR")" && pwd)"

# Check if we're in a git repo (development mode)
if [[ -d "$REPO_ROOT/.git" ]]; then
    INSTALL_MODE="development"
    echo -e "${GREEN}✓${NC} Mode: Development (git repo detected)"
    echo "  Source: $REPO_ROOT"
else
    INSTALL_MODE="release"
    echo -e "${GREEN}✓${NC} Mode: Release (pip install)"
fi

# Create ~/.hero/ directory
HERO_HOME="$HOME/.hero"
mkdir -p "$HERO_HOME/sandboxes"
echo -e "${GREEN}✓${NC} Created $HERO_HOME/"

# Install hero CLI
echo ""
if [[ "$INSTALL_MODE" == "development" ]]; then
    echo "Installing hero CLI in development mode..."
    cd "$REPO_ROOT"
    if [[ "$UV_AVAILABLE" == true ]]; then
        uv pip install -e .
    else
        pip install -e .
    fi
else
    echo "Installing hero CLI from PyPI..."
    if [[ "$UV_AVAILABLE" == true ]]; then
        uv pip install hero
    else
        pip install hero
    fi
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Run ${GREEN}hero scan${NC} to discover projects in ~/Development/"
echo "  2. Run ${GREEN}hero status${NC} to see all sandboxes"
echo "  3. Run ${GREEN}hero spawn --sandbox <name> --task \"<task>\"${NC} to launch a soldier"
echo ""
echo "Documentation:"
echo "  ${GREEN}hero --help${NC}     Show all commands"
echo "  ${GREEN}hero <cmd> --help${NC}  Show help for specific command"
echo ""