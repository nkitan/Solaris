# Solaris ☀️🌙

**Solar-aware GNOME theme orchestration for Arch Linux.**

Solaris automatically switches your GTK, GNOME Shell, and Firefox themes at sunrise and sunset — using systemd user timers, not a background daemon.

---

## Features

- 🌅 **Solar-aware switching** — calculates local sunrise/sunset via the `astral` library
- 🎨 **Full theme control** — GTK theme, GNOME Shell theme, and `color-scheme` gsetting
- 🦊 **Firefox integration** — patches `userChrome.css` with matching background/text colours
- ⏱️ **No daemon** — two self-rescheduling systemd user units replace a long-running process
- 🖥️ **Native GNOME UI** — built with PyGObject + Libadwaita for a seamless Settings-like feel
- 📍 **Location detection** — uses GeoClue2 for automatic coordinate detection

---

## Architecture

```
solaris/
├── config.py           # XDG config management (~/.config/solaris/config.json)
├── theme_engine.py     # gsettings wrapper (GTK + Shell + color-scheme)
├── firefox.py          # userChrome.css patcher
├── solar.py            # astral sunrise/sunset calculator
├── systemd_manager.py  # systemd user unit generator and controller
├── cli.py              # CLI entry point (used by the systemd service)
├── app.py              # Adw.Application GUI entry point
└── ui/
    ├── status_page.py       # Dashboard: mode display, override, countdown
    └── preferences_page.py  # Settings: themes, location, Firefox
```

### The Self-Rescheduling Timer Pattern

Instead of a daemon, Solaris uses two systemd user units:

- **`solaris-update.service`** — a oneshot service that runs `solaris --auto`
- **`solaris-update.timer`** — fires at today's sunrise and sunset times

When the timer fires, `solaris --auto`:
1. Calculates the current solar position → applies the correct theme
2. Patches Firefox `userChrome.css`
3. Rewrites the timer with **tomorrow's** sunrise/sunset times

This keeps the schedule perpetually up-to-date with no manual intervention.

---

## Installation

### Prerequisites

```bash
# Arch Linux packages
sudo pacman -S python python-gobject libadwaita gtk4

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install from source

```bash
git clone https://github.com/notroot/solaris
cd solaris
uv sync
```

---

## Usage

### GUI

```bash
uv run solaris-gui
```

### CLI

```bash
# Show current status
uv run solaris --status

# Force apply a theme immediately
uv run solaris --apply-light
uv run solaris --apply-dark

# Apply based on current solar position (used by systemd)
uv run solaris --auto

# Install and enable the systemd timer
uv run solaris --install-timer

# Recalculate and update the timer schedule
uv run solaris --update-timer
```

---

## Firefox Integration

Solaris patches `userChrome.css` in your active Firefox profile. It looks for a block delimited by:

```css
/* SOLARIS_THEME_START */
:root {
  --solaris-bg: #ffffff;
  --solaris-text: #000000;
}
/* SOLARIS_THEME_END */
```

If the block doesn't exist, it is appended automatically. A `.bak` backup is created before every modification.

To enable userChrome.css in Firefox, navigate to `about:config` and set:
```
toolkit.legacyUserProfileCustomizations.stylesheets = true
```

---

## Configuration

Config is stored at `~/.config/solaris/config.json`:

```json
{
  "latitude": 18.5,
  "longitude": 73.8,
  "light_gtk_theme": "Colloid-Light",
  "dark_gtk_theme": "Colloid-Dark",
  "light_shell_theme": "Colloid-Light",
  "dark_shell_theme": "Colloid-Dark",
  "light_color_scheme": "prefer-light",
  "dark_color_scheme": "prefer-dark",
  "firefox_integration": true,
  "override_mode": null
}
```

---

## Systemd Units

After running `solaris --install-timer`, two unit files are created in `~/.config/systemd/user/`:

**`solaris-update.service`** — executes `solaris --auto`
**`solaris-update.timer`** — fires at today's sunrise and sunset

Check timer status:
```bash
systemctl --user status solaris-update.timer
journalctl --user -u solaris-update.service
```

---

## License

MIT
