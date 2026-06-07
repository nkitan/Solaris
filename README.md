# Solaris ☀️🌙

**Solar-aware GNOME theme orchestration for Linux.**

Solaris is a modern, lightweight utility designed to seamlessly transition your system and applications between dark and light themes. It calculates your local sunrise and sunset times automatically or follows your global GNOME theme preference in real time.

Unlike bulky daemons, Solaris handles background scheduling using native systemd user timers (the "self-rescheduling timer pattern") or runs a lightweight event watcher to listen to D-Bus/GSettings signals.

Solaris works on any Linux distribution running **GNOME with systemd**. The installer auto-detects your distro family (Arch, Debian/Ubuntu, Fedora, openSUSE, NixOS) and adapts accordingly.

---

## 🚀 Features & Integrations

Solaris features deep integration across the entire Linux desktop stack, ensuring that when the sun sets, your workspace changes with it:

*   🌅 **Solar-Aware Switching** — Calculates exact daily sunrise and sunset coordinates using the `astral` library.
*   🎨 **GNOME Desktop Alignment** — Coordinates GTK theme, GNOME Shell theme, and the system-wide `color-scheme` preference.
*   🦊 **Firefox Integration** — Patches your active Firefox profile's `userChrome.css` dynamically to switch background and text variables.
*   👻 **Ghostty Integration** — Updates Ghostty terminal themes live and sends a `SIGUSR2` signal to active Ghostty instances so they redraw instantly without losing your shell state.
*   🌐 **Chrome, Chromium & Electron Apps** — Out of the box, Chrome and Electron apps set to "Use System Theme" or GTK mode will automatically inherit GNOME's theme state when Solaris changes it.
*   👀 **Real-Time Watcher** — Listens to global GNOME Quick Settings quick-toggles and updates all your apps in real time.
*   🖥️ **Native Libadwaita GUI** — A polished, settings-like GTK4 dashboard built with PyGObject.
*   📍 **Automatic Location** — Detects your latitude and longitude automatically via GeoClue2.

---

## 🛠️ Prerequisites

Before installing Solaris, ensure your system has the required dependencies. The installer detects your distro and prints the right package list if anything is missing — but you can install them ahead of time:

**Arch Linux / Manjaro / EndeavourOS:**
```bash
sudo pacman -S --needed python python-gobject libadwaita gtk4 git
```

**Debian / Ubuntu / Pop!_OS / Linux Mint (24.04+ / 13+):**
```bash
sudo apt install -y python3 python3-gi libadwaita-1-0 libgtk-4-1 git
```

**Fedora / Nobara:**
```bash
sudo dnf install -y python3 python3-gobject libadwaita gtk4 git
```

**openSUSE:**
```bash
sudo zypper install -y python3 python3-gobject libadwaita-1 gtk4 git
```

**NixOS:** add the following to `environment.systemPackages` (or `home.packages`) in `configuration.nix`:
```nix
pkgs.python3 pkgs.python3Packages.pygobject pkgs.libadwaita pkgs.gtk4 pkgs.git
```

**uv (Modern Python Package Manager)** — used on all distros:
It is recommended to use `uv` for managing python tools and environments. Install it via:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> **Note:** The Python/GUI core is distro-agnostic — it talks to GNOME through GSettings/D-Bus, schedules with `systemd --user`, and writes theme files into `~/.config`. As long as GNOME + systemd + the runtime deps above are present, Solaris will work.

---

## 📦 Installation & Setup

### Option 1: Production Install (Recommended)

To install Solaris for daily production use, clone the repository and run the provided automated installation script:

```bash
git clone https://github.com/notroot/solaris.git
cd solaris
./install.sh
```

The [install.sh](file:///home/notroot/Work/Solaris/install.sh) script will:
1.  Verify the presence of `uv`, `git`, and system dependencies.
2.  Install `solaris` and `solaris-gui` into your user tool path via `uv tool install`.
3.  Install custom application icons (SVG and PNG formats) from `public/favicon` into the user's local icon directory (`~/.local/share/icons/hicolor/`), supporting automatic light/dark adaptive rendering.
4.  Generate and place a desktop entry at `~/.local/share/applications/solaris.desktop` so you can launch Solaris GUI straight from your GNOME Applications Overview dashboard.

### Option 2: Development Install

If you are developing or modifying Solaris, set up a local virtual environment:

```bash
git clone https://github.com/notroot/solaris.git
cd solaris

# Create a virtual environment and sync all dependencies
uv venv
source .venv/bin/activate
uv sync
```

You can then run the commands locally:
*   Launch CLI: `uv run solaris --help`
*   Launch GUI: `uv run solaris-gui`

---

## 🖥️ Using the GUI

Once installed, you can launch the GUI in two ways:
*   **GNOME Shell Menu:** Search for **"Solaris"** in your application launcher.
*   **Terminal:** Run `solaris-gui`.

The Libadwaita GUI provides:
*   **Status Page:** Displays current mode (Light/Dark), schedule configuration, coordinates, and a countdown timer for the next transition. It also contains an **"Override"** switch for quick manual overrides.
*   **Preferences Page:** Allows you to select light/dark theme variants for GTK, GNOME Shell, Firefox, and Ghostty. You can also edit location coordinates manually or click **"Detect Location"** to fetch them automatically via D-Bus.

---

## ⚙️ How Theme Integration Works

### 🦊 Firefox
Solaris modifies `userChrome.css` inside your active profile. It searches for or appends a custom block:
```css
/* SOLARIS_THEME_START */
:root {
  --solaris-bg: #ffffff;
  --solaris-text: #000000;
}
/* SOLARIS_THEME_END */
```
To enable this stylesheet in Firefox, navigate to `about:config` and set:
```text
toolkit.legacyUserProfileCustomizations.stylesheets = true
```

### 👻 Ghostty
Solaris patches your `~/.config/ghostty/config` file in a dedicated block:
```text
# SOLARIS_THEME_START
theme = Catppuccin Latte
window-theme = ghostty
window-decoration = auto
# SOLARIS_THEME_END
```
It then sends `SIGUSR2` to all running Ghostty processes to trigger an instant hot-reload of configurations.

### 🌐 Chrome / Chromium / Electron
These applications automatically pick up the GTK and system dark/light configuration. Ensure Chrome is set to **Classic** or **GTK** theme under *Settings -> Appearance*, and it will switch automatically when Solaris updates GNOME's theme keys.

---

## ⏱️ Background Services & Watcher

Solaris offers two ways to sync themes automatically in the background:

### 1. Solar Schedule (Self-Rescheduling Systemd Timer)
Instead of running a daemon constantly, Solaris creates two user-level systemd units to schedule updates exactly at sunrise and sunset:

To install and enable the timer:
```bash
solaris --install-timer
```
This sets up:
*   `solaris-update.service` — A oneshot service that executes `solaris --auto`.
*   `solaris-update.timer` — Fires at today's sunrise/sunset. When it triggers, `solaris --auto` runs, changes the theme, and rewrites the timer unit with **tomorrow's** solar times.

### 2. Real-Time GNOME Theme Watcher
If you want applications (like Firefox and Ghostty) to immediately adapt to manual switches you make via the GNOME Quick Settings "Dark Style" button:

Enable the real-time watcher service:
```bash
# Enable in GSettings & systemd
systemctl --user enable --now solaris-watcher.service
```

This runs a lightweight GSettings subscriber (`solaris --watch`) that blocks on changes to the GNOME `org.gnome.desktop.interface color-scheme` key. The moment it detects a toggle, it propagates themes to Firefox, Ghostty, GTK, and shell themes instantly.

You can check unit statuses using:
```bash
# Check timer state
systemctl --user status solaris-update.timer
# Check watcher daemon status
systemctl --user status solaris-watcher.service
# Check service log history
journalctl --user -u solaris-update.service -n 50 --no-pager
```

---

## 💻 CLI Usage Reference

```bash
# Show current status, location, schedule, timer, and watcher states
solaris --status

# Force apply a theme state immediately across all integrations
solaris --apply-light
solaris --apply-dark

# Switch dynamically based on current solar position or scheduled window
solaris --auto

# Generate and register the systemd timer
solaris --install-timer

# Force recalculate times and rewrite the timer schedule
solaris --update-timer

# Run the real-time GSettings watcher (used by solaris-watcher.service)
solaris --watch
```

---

## 📄 License

MIT
