# Solaris — Development TODO

> Tick off each item as you complete it. Sub-items are optional but recommended.

---

## Phase 1 — Project Scaffolding
- [ ] Update `pyproject.toml` with proper description, `[project.scripts]`, and `[project.gui-scripts]`
- [ ] Create `solaris/__init__.py` with `__version__`
- [ ] Delete placeholder `main.py`
- [ ] Verify `uv run solaris --help` resolves correctly

## Phase 2 — Configuration Layer
- [ ] Create `solaris/config.py` with `SolarisConfig` dataclass
- [ ] Implement `load()` — JSON → dataclass (create default if missing)
- [ ] Implement `save()` — atomic write (write-to-temp, rename)
- [ ] Use `pyxdg` for `XDG_CONFIG_HOME/solaris/config.json`
- [ ] Write unit tests for config round-trip and defaults

## Phase 3 — Core Engine Modules

### 3A — Theme Engine (`solaris/theme_engine.py`)
- [ ] Implement `apply_light()` — set gsettings for GTK theme, color-scheme, shell theme
- [ ] Implement `apply_dark()` — same as above for dark variants
- [ ] Implement `get_current_mode()` — read `color-scheme` from gsettings
- [ ] Implement `scan_themes()` — list `/usr/share/themes/` filtered by prefix
- [ ] Gracefully handle missing User Themes GNOME extension (warn, don't crash)
- [ ] Write unit tests (mock subprocess)

### 3B — Firefox Integration (`solaris/firefox.py`)
- [ ] Implement `find_active_profile()` — parse `profiles.ini` for `Default=1`
- [ ] Implement `apply_theme()` — find/replace hex codes in `userChrome.css`
- [ ] Handle `SOLARIS_THEME_START` / `SOLARIS_THEME_END` marker blocks
- [ ] Append default template if markers don't exist
- [ ] Implement `ensure_user_chrome_dir()` — create `chrome/` if missing
- [ ] Return `False` (don't raise) if Firefox not installed or no profile found
- [ ] Write unit tests with sample CSS strings

### 3C — Solar Calculator (`solaris/solar.py`)
- [ ] Implement `SolarCalculator.__init__()` with lat/lon
- [ ] Implement `get_times()` — sunrise/sunset for a given date using `astral`
- [ ] Implement `get_current_mode()` — "light" if between sunrise and sunset
- [ ] Implement `next_transition()` — returns (event_name, datetime) for next switch
- [ ] Write unit tests with known reference values

### 3D — Systemd Manager (`solaris/systemd_manager.py`)
- [ ] Define service unit template (`solaris-update.service`)
- [ ] Define timer unit template (`solaris-update.timer`) with dual `OnCalendar`
- [ ] Implement `install_units()` — write files + `daemon-reload`
- [ ] Implement `update_timer()` — recalculate `OnCalendar` + reload
- [ ] Implement `enable()` / `disable()` / `is_enabled()` / `trigger_now()`
- [ ] Write unit tests (verify generated file content)

## Phase 4 — CLI Entry Point (`solaris/cli.py`)
- [ ] Set up `argparse` with mutually exclusive flags
- [ ] Implement `--apply-light` handler
- [ ] Implement `--apply-dark` handler
- [ ] Implement `--auto` handler (solar calc → apply → update timer)
- [ ] Implement `--status` handler (current mode, next transition, timer status)
- [ ] Implement `--install-timer` handler
- [ ] Implement `--update-timer` handler
- [ ] Verify `uv run solaris --status` works end-to-end

## Phase 5 — Libadwaita GUI

### 5A — Application Shell (`solaris/app.py`)
- [ ] Create `Adw.Application` subclass with app ID `io.github.solaris`
- [ ] Set up `Adw.ApplicationWindow` with `Adw.HeaderBar`
- [ ] Add view switching between Status and Preferences pages
- [ ] Wire up application activation and window presentation

### 5B — Status Page (`solaris/ui/status_page.py`)
- [ ] Create `Adw.StatusPage` with sun/moon icon based on current mode
- [ ] Add Override toggle (`Adw.SwitchRow`) with Light/Dark dropdown
- [ ] Add "Next Transition" countdown row (updated every 60s via `GLib.timeout_add_seconds`)
- [ ] Add "Apply Now" button with `suggested-action` style class
- [ ] Add systemd timer status row with Enable/Disable button
- [ ] Wire all widgets to config and core modules

### 5C — Preferences Page (`solaris/ui/preferences_page.py`)
- [ ] Create Theme preferences group with 4 `Adw.ComboRow` dropdowns (Light/Dark × GTK/Shell)
- [ ] Populate dropdowns from `scan_themes()`
- [ ] Create Location preferences group with Latitude/Longitude `Adw.EntryRow`
- [ ] Add "Detect Location" button using GeoClue2 D-Bus
- [ ] Create Firefox preferences group with integration toggle and detected profile display
- [ ] Wire all widgets to config save/load

### 5D — GUI Polish
- [ ] Test GUI launch: `uv run solaris-gui`
- [ ] Verify all combo rows populate correctly
- [ ] Verify override toggle persists across restarts
- [ ] Verify countdown updates in real-time
- [ ] Test with GNOME dark mode and light mode for visual consistency

## Phase 6 — Documentation
- [ ] Update `AGENTS.md` — tailored to Solaris project
- [ ] Update `GEMINI.md` — Solaris-specific coding context
- [ ] Update `README.md` — project overview, installation, usage, architecture
- [ ] Update `.gitignore` — add Solaris-specific patterns

## Phase 7 — Integration Testing & Verification
- [ ] `uv run solaris --status` — prints mode + next transition
- [ ] `uv run solaris --apply-light` — visually confirm theme change
- [ ] `uv run solaris --apply-dark` — visually confirm theme change
- [ ] `uv run solaris --install-timer` — verify systemd timer is active
- [ ] `uv run solaris-gui` — full GUI smoke test
- [ ] Verify Firefox `userChrome.css` patching
- [ ] Run full test suite: `uv run pytest`

---

*Last updated: 2026-05-12*
