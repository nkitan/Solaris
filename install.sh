#!/usr/bin/env bash
set -euo pipefail

echo "============================================="
echo "        Solaris Installer                    "
echo "============================================="

# ---------------------------------------------------------------------------
# Distro detection
# ---------------------------------------------------------------------------
# Identifies the host's distro family (arch, debian, fedora, suse, nixos,
# unknown) by reading /etc/os-release. Used to pick the right package
# manager and package names for GNOME runtime deps.
# ---------------------------------------------------------------------------
detect_distro() {
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
    fi

    case "${ID:-}${ID_LIKE:-}" in
        *arch*|*manjaro*|*endeavour*) echo "arch" ;;
        *debian*|*ubuntu*|*pop*|*mint*|*elementary*|*zorin*) echo "debian" ;;
        *fedora*|*nobara*) echo "fedora" ;;
        *suse*|*opensuse*) echo "suse" ;;
        *nixos*) echo "nixos" ;;
        *) echo "unknown" ;;
    esac
}

# Returns the native package manager command for the detected distro.
pkg_manager() {
    case "$1" in
        arch)   echo "pacman"  ;;
        debian) echo "apt"     ;;
        fedora) echo "dnf"     ;;
        suse)   echo "zypper"  ;;
        *)      echo ""        ;;
    esac
}

# Returns a shell snippet (with the right package names) that installs the
# GNOME runtime dependencies Solaris needs. Empty for unknown/nixos.
pkg_install_cmd() {
    case "$1" in
        arch)
            echo "sudo pacman -S --needed python python-gobject libadwaita gtk4"
            ;;
        debian)
            # libadwaita-1-0 ships in Debian 13+ / Ubuntu 24.04+
            echo "sudo apt install -y python3 python3-gi libadwaita-1-0 libgtk-4-1"
            ;;
        fedora)
            echo "sudo dnf install -y python3 python3-gobject libadwaita gtk4"
            ;;
        suse)
            echo "sudo zypper install -y python3 python3-gobject libadwaita-1 gtk4"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Checks whether each required GNOME package is already installed.
# Returns 0 (success) if all are present, 1 if any are missing.
# Uses the distro's package manager to query the system.
check_runtime_deps() {
    local distro="$1"
    case "$distro" in
        arch)
            pacman -Qq python-gobject libadwaita gtk4 &> /dev/null
            ;;
        debian)
            local missing=0
            for pkg in python3-gi libadwaita-1-0 libgtk-4-1; do
                if ! dpkg -s "$pkg" &> /dev/null; then missing=1; fi
            done
            return $missing
            ;;
        fedora)
            rpm -q python3-gobject libadwaita gtk4 &> /dev/null
            ;;
        suse)
            rpm -q python3-gobject libadwaita-1 gtk4 &> /dev/null
            ;;
        *)
            return 0  # can't check, assume ok
            ;;
    esac
}

DISTRO="$(detect_distro)"
echo "Detected distro family: ${DISTRO}"

# ---------------------------------------------------------------------------
# 1. Prerequisite Checks
# ---------------------------------------------------------------------------
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
    PM="$(pkg_manager "$DISTRO")"
    case "$DISTRO" in
        arch)   echo "  Please install git: sudo pacman -S git" ;;
        debian) echo "  Please install git: sudo apt install git" ;;
        fedora) echo "  Please install git: sudo dnf install git" ;;
        suse)   echo "  Please install git: sudo zypper install git" ;;
        *)      echo "  Please install git using your distro's package manager ($PM)." ;;
    esac
    exit 1
else
    echo "✓ 'git' is installed."
fi

# PyGObject / libadwaita / GTK4 runtime — required for the GUI on every distro.
echo "Checking GNOME runtime dependencies..."
if check_runtime_deps "$DISTRO"; then
    echo "✓ GNOME runtime dependencies found."
else
    INSTALL_CMD="$(pkg_install_cmd "$DISTRO")"
    echo "⚠️  Some GNOME runtime dependencies might be missing."
    if [ -n "$INSTALL_CMD" ]; then
        echo "  Install them with:"
        echo "    $INSTALL_CMD"
    elif [ "$DISTRO" = "nixos" ]; then
        echo "  On NixOS, add these to configuration.nix environment.systemPackages:"
        echo "    pkgs.python3 pkgs.python3Packages.pygobject pkgs.libadwaita pkgs.gtk4"
    else
        echo "  Please install: python3 (with PyGObject/GI bindings), libadwaita, and GTK4."
    fi
fi

# ---------------------------------------------------------------------------
# 2. Build and Install via uv tool
# ---------------------------------------------------------------------------
echo "Installing Solaris using 'uv tool install'..."
uv tool install --force .

# ---------------------------------------------------------------------------
# 3. Install Icons
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 4. Desktop Application Entry Creation
# ---------------------------------------------------------------------------
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
