#!/usr/bin/env bash
set -euo pipefail

echo "============================================="
echo "        Solaris Installer                    "
echo "============================================="

# 1. Prerequisite Checks
echo "Checking prerequisites..."

if ! command -v uv &> /dev/null; then
    echo "✖ 'uv' is not installed."
    echo "  Please install uv first (e.g. curl -LsSf https://astral.sh/uv/install.sh | sh)"
    exit 1
else
    echo "✓ 'uv' is installed."
fi

if ! command -v git &> /dev/null; then
    echo "✖ 'git' is not installed."
    echo "  Please install git via pacman (e.g. sudo pacman -S git)"
    exit 1
else
    echo "✓ 'git' is installed."
fi

# Check PyGObject dependencies which are required on Arch Linux
echo "Checking GNOME dependencies (python-gobject, libadwaita)..."
if pacman -Qq python-gobject libadwaita gtk4 &> /dev/null; then
    echo "✓ GNOME system dependencies found."
else
    echo "⚠️  Some GNOME dependencies might be missing."
    echo "  Please ensure they are installed: sudo pacman -S python-gobject libadwaita gtk4"
fi

# 2. Build and Install via uv tool
echo "Installing Solaris using 'uv tool install'..."
uv tool install --force .

# 3. Install Icons
echo "Installing application icons..."
ICON_THEME_DIR="$HOME/.local/share/icons/hicolor"
mkdir -p "$ICON_THEME_DIR/scalable/apps"
mkdir -p "$ICON_THEME_DIR/symbolic/apps"
mkdir -p "$ICON_THEME_DIR/96x96/apps"
mkdir -p "$ICON_THEME_DIR/192x192/apps"
mkdir -p "$ICON_THEME_DIR/512x512/apps"

# Copy SVG icons
cp public/favicon/favicon.svg "$ICON_THEME_DIR/scalable/apps/io.github.solaris.svg"
cp public/favicon/favicon.svg "$ICON_THEME_DIR/symbolic/apps/io.github.solaris-symbolic.svg"

# Copy PNG icons
cp public/favicon/favicon-96x96.png "$ICON_THEME_DIR/96x96/apps/io.github.solaris.png"
cp public/favicon/web-app-manifest-192x192.png "$ICON_THEME_DIR/192x192/apps/io.github.solaris.png"
cp public/favicon/web-app-manifest-512x512.png "$ICON_THEME_DIR/512x512/apps/io.github.solaris.png"

# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    echo "Updating GTK icon cache..."
    gtk-update-icon-cache -f -t "$ICON_THEME_DIR" || true
fi

# 4. Desktop Application Entry Creation
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
DESKTOP_FILE="$DESKTOP_DIR/solaris.desktop"
rm -f "$DESKTOP_DIR/io.github.solaris.desktop"

# Locate the installed gui command path (default to local bin)
SOLARIS_GUI_PATH="$HOME/.local/bin/solaris-gui"
if [ ! -f "$SOLARIS_GUI_PATH" ]; then
    SOLARIS_GUI_PATH="solaris-gui"
fi

echo "Generating desktop entry: $DESKTOP_FILE"
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=Solaris
Comment=Solar-aware GNOME theme orchestrator
Exec=${SOLARIS_GUI_PATH}
Icon=io.github.solaris
Terminal=false
Type=Application
Categories=Utility;Settings;GTK;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

echo "---------------------------------------------"
echo "✓ Solaris CLI ('solaris') and GUI ('solaris-gui') successfully installed!"
echo "✓ Desktop application entry added."
echo "  You can launch the GUI via the application launcher (search for 'Solaris')."
echo "============================================="
