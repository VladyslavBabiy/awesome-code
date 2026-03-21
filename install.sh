#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/.awesome-code"
VENV_DIR="$INSTALL_DIR/venv"
BIN_LINK="/usr/local/bin/awesome-code"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        AwesomeCode Installer           ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Check Python 3.10+
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Install it with: brew install python"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "❌ Python 3.10+ required (found $PY_VERSION)"
    exit 1
fi

echo "✓ Python $PY_VERSION"

# Create install directory
mkdir -p "$INSTALL_DIR"

# Create or update venv
if [ ! -d "$VENV_DIR" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "→ Virtual environment exists, updating..."
fi

# Install awesome-code into venv
echo "→ Installing awesome-code..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -e "$REPO_DIR" -q

# Create wrapper script
WRAPPER="$INSTALL_DIR/bin/awesome-code"
mkdir -p "$INSTALL_DIR/bin"
cat > "$WRAPPER" << 'SCRIPT'
#!/usr/bin/env bash
exec "$HOME/.awesome-code/venv/bin/awesome-code" "$@"
SCRIPT
chmod +x "$WRAPPER"

# Symlink to /usr/local/bin (or ~/bin as fallback)
if [ -w "/usr/local/bin" ]; then
    ln -sf "$WRAPPER" "$BIN_LINK"
    echo "✓ Linked to $BIN_LINK"
else
    # Try with sudo
    echo "→ Need sudo to link to /usr/local/bin..."
    if sudo ln -sf "$WRAPPER" "$BIN_LINK" 2>/dev/null; then
        echo "✓ Linked to $BIN_LINK"
    else
        # Fallback: add to PATH via shell profile
        FALLBACK_BIN="$HOME/.local/bin"
        mkdir -p "$FALLBACK_BIN"
        ln -sf "$WRAPPER" "$FALLBACK_BIN/awesome-code"
        echo "✓ Linked to $FALLBACK_BIN/awesome-code"

        # Add to PATH if not already there
        if [[ ":$PATH:" != *":$FALLBACK_BIN:"* ]]; then
            SHELL_RC="$HOME/.zshrc"
            [ -f "$HOME/.bashrc" ] && [ ! -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.bashrc"
            echo "export PATH=\"$FALLBACK_BIN:\$PATH\"" >> "$SHELL_RC"
            echo "→ Added $FALLBACK_BIN to PATH in $SHELL_RC"
            echo "  Run: source $SHELL_RC"
        fi
    fi
fi

echo ""
echo "  ✅ AwesomeCode installed!"
echo ""
echo "  Usage:"
echo "    cd your-project/"
echo "    awesome-code"
echo ""
echo "  First run will ask for your OpenRouter API key."
echo "  Get one at: https://openrouter.ai/keys"
echo ""
