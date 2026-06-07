# Solaris — Development TODO

> Tick off each item as you complete it. Sub-items are optional but recommended.

---

## Phase 1 — Project Scaffolding
- [x] Update `pyproject.toml` with proper description, `[project.scripts]`, and `[project.gui-scripts]`
- [x] Create `solaris/__init__.py` with `__version__`
- [x] Delete placeholder `main.py`
- [x] Verify `uv run solaris --help` resolves correctly

## Phase 2 — Configuration Layer
- [x] Create `solaris/config.py` with `SolarisConfig` dataclass
- [x] Implement `load()` — JSON → dataclass (create default if missing)
- [x] Implement `save()` — atomic write (write-to-temp, rename)
- [x] Use `pyxdg` for `XDG_CONFIG_HOME/solaris/config.json`
- [x] Write unit tests for config round-trip and defaults

## Phase 3 — Core Engine Modules

### 3A — Theme Engine (`solaris/theme_engine.py`)
- [x] Implement `apply_light()` — set gsettings for GTK theme, color-scheme, shell theme
- [x] Implement `apply_dark()` — same as above for dark variants
- [x] Implement `get_current_mode()` — read `color-scheme` from gsettings
- [x] Implement `scan_themes()` — list `/usr/share/themes/` filtered by prefix
- [x] Gracefully handle missing User Themes GNOME extension (warn, don't crash)
- [x] Write unit tests (mock subprocess)

### 3B — Firefox Integration (`solaris/firefox.py`)
- [x] Implement `find_active_profile()` — parse `profiles.ini` for `Default=1`
- [x] Implement `apply_theme()` — find/replace hex codes in `userChrome.css`
- [x] Handle `SOLARIS_THEME_START` / `SOLARIS_THEME_END` marker blocks
- [x] Append default template if markers don't exist
- [x] Implement `ensure_user_chrome_dir()` — create `chrome/` if missing
- [x] Return `False` (don't raise) if Firefox not installed or no profile found
- [x] Write unit tests with sample CSS strings

### 3C — Solar Calculator (`solaris/solar.py`)
- [x] Implement `SolarCalculator.__init__()` with lat/lon
- [x] Implement `get_times()` — sunrise/sunset for a given date using `astral`
- [x] Implement `get_current_mode()` — "light" if between sunrise and sunset
- [x] Implement `next_transition()` — returns (event_name, datetime) for next switch
- [x] Write unit tests with known reference values

### 3D — Systemd Manager (`solaris/systemd_manager.py`)
- [x] Define service unit template (`solaris-update.service`)
- [x] Define timer unit template (`solaris-update.timer`) with dual `OnCalendar`
- [x] Implement `install_units()` — write files + `daemon-reload`
- [x] Implement `update_timer()` — recalculate `OnCalendar` + reload
- [x] Implement `enable()` / `disable()` / `is_enabled()` / `trigger_now()`
- [x] Write unit tests (verify generated file content)

## Phase 4 — CLI Entry Point (`solaris/cli.py`)
- [x] Set up `argparse` with mutually exclusive flags
- [x] Implement `--apply-light` handler
- [x] Implement `--apply-dark` handler
- [x] Implement `--auto` handler (solar calc → apply → update timer)
- [x] Implement `--status` handler (current mode, next transition, timer status)
- [x] Implement `--install-timer` handler
- [x] Implement `--update-timer` handler
- [x] Verify `uv run solaris --status` works end-to-end

## Phase 5 — Libadwaita GUI

### 5A — Application Shell (`solaris/app.py`)
- [x] Create `Adw.Application` subclass with app ID `io.github.solaris`
- [x] Set up `Adw.ApplicationWindow` with `Adw.HeaderBar`
- [x] Add view switching between Status and Preferences pages
- [x] Wire up application activation and window presentation

### 5B — Status Page (`solaris/ui/status_page.py`)
- [x] Create `Adw.StatusPage` with sun/moon icon based on current mode
- [x] Add Override toggle (`Adw.SwitchRow`) with Light/Dark dropdown
- [x] Add "Next Transition" countdown row (updated every 60s via `GLib.timeout_add_seconds`)
- [x] Add "Apply Now" button with `suggested-action` style class
- [x] Add systemd timer status row with Enable/Disable button
- [x] Wire all widgets to config and core modules

### 5C — Preferences Page (`solaris/ui/preferences_page.py`)
- [x] Create Theme preferences group with 4 `Adw.ComboRow` dropdowns (Light/Dark × GTK/Shell)
- [x] Populate dropdowns from `scan_themes()`
- [x] Create Location preferences group with Latitude/Longitude `Adw.EntryRow`
- [x] Add "Detect Location" button using GeoClue2 D-Bus
- [x] Create Firefox preferences group with integration toggle and detected profile display
- [x] Wire all widgets to config save/load

### 5D — GUI Polish
- [x] Test GUI launch: `uv run solaris-gui`
- [x] Verify all combo rows populate correctly
- [x] Verify override toggle persists across restarts
- [x] Verify countdown updates in real-time
- [x] Test with GNOME dark mode and light mode for visual consistency

## Phase 6 — Documentation
- [x] Update `AGENTS.md` — tailored to Solaris project
- [x] Update `GEMINI.md` — Solaris-specific coding context
- [x] Update `README.md` — project overview, installation, usage, architecture
- [x] Update `.gitignore` — add Solaris-specific patterns

## Phase 7 — Integration Testing & Verification
- [x] `uv run solaris --status` — prints mode + next transition
- [x] `uv run solaris --apply-light` — visually confirm theme change
- [x] `uv run solaris --apply-dark` — visually confirm theme change
- [x] `uv run solaris --install-timer` — verify systemd timer is active
- [x] `uv run solaris-gui` — full GUI smoke test
- [x] Verify Firefox `userChrome.css` patching
- [x] Run full test suite: `uv run pytest`

---

*Last updated: 2026-06-07*
