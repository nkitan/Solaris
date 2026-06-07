# AGENTS.md — Project Rules for AI Coding Agents
# This file is read by Antigravity (v1.20.3+), Cursor, and Claude Code.
# Rules here apply to all tools. Antigravity-specific overrides go in GEMINI.md.

## Project Overview
- **Name:** Solaris
- **Type:** GNOME-native desktop application (GTK4 GUI + CLI + systemd user units)
- **Stage:** Active Development (MVP, v0.1.0)
- **Purpose:** Solar-aware theme orchestration for Linux — automatically switches
  GTK/Shell themes, Firefox `userChrome.css`, and Ghostty `config` at sunrise/sunset
  (or at user-defined fixed times), and reacts in real time to the GNOME "Dark Style"
  quick-settings toggle. Driven by self-rescheduling systemd user timers or a
  long-running GSettings watcher.

## Tech Stack
- **Language:** Python 3.13+ (strict typing with `from __future__ import annotations`)
- **Package Manager:** uv (tool install, venv, lockfile). `uv.lock` is git-ignored.
- **GUI Framework:** PyGObject (gi) with Libadwaita (GTK4) — uses `Adw.Application`,
  `Adw.ViewStack`, `Adw.PreferencesPage`, `Adw.ComboRow`/`SwitchRow`/`EntryRow`.
- **Key Libraries:** astral (solar math), pyxdg (XDG paths), gi (Gio/GLib/Adw).
- **System Integration:** `gsettings` (dconf) via subprocess, `systemd --user`
  timer/service units, Firefox `userChrome.css` patch, Ghostty `config` patch +
  `SIGUSR2` reload.
- **Testing:** pytest + pytest-mock + pytest-cov. Tests live in `tests/`.
- **Target OS:** Any Linux distro running **GNOME + systemd** (Arch, Manjaro,
  EndeavourOS, Debian, Ubuntu, Pop!_OS, Linux Mint, Fedora, Nobara, openSUSE,
  NixOS). `install.sh` auto-detects the family and picks the right package
  manager; only GNOME 46+ is exercised in practice.

## Code Quality
- Soft target ≤ 300 lines per file; hard cap 400. Split if you exceed it.
  Current exceptions to know about: `cli.py` (348), `systemd_manager.py` (352),
  `solaris/ui/preferences_page.py` (513), `solaris/ui/status_page.py` (448).
- Maximum function length: 30 lines.
- **No comments in code** unless the user explicitly asks for one. Docstrings
  are encouraged; inline `#` commentary is not.
- No `print()` in library code — use Python `logging` module.
- CLI (`cli.py`) and GUI (`app.py`) entry points are the **only** places that
  configure log handlers (`logging.basicConfig`). All other modules just call
  `logger = logging.getLogger(__name__)`.
- Use `@dataclass` for structured data, `NamedTuple` for immutable records.
- All public functions and classes must have docstrings (Google style —
  `Args:` / `Returns:` / `Raises:`).
- Type hints on all function signatures — no `Any` unless absolutely necessary.
- Prefer `Path` objects over string paths.
- `subprocess.run()` is the default: always `capture_output=True, text=True,
  check=False`, and check `returncode` + log `stderr` on failure.

## Module Boundaries (Critical)
- **`solaris/config.py`** — ONLY reads/writes JSON config. No gsettings, no
  subprocess, no I/O outside `~/.config/solaris/`. Defines the `SolarisConfig`
  dataclass and the three `SCHEDULE_MODE_*` constants.
- **`solaris/theme_engine.py`** — ONLY talks to gsettings. Receives config
  values as parameters. Uses `subprocess.run(["gsettings", ...])` deliberately
  (not `Gio.Settings`) so the optional `org.gnome.shell.extensions.user-theme`
  schema is never required.
- **`solaris/firefox.py`** — ONLY patches `chrome/userChrome.css` inside the
  active Firefox profile. Owns the `SOLARIS_THEME_START/END` marker block.
- **`solaris/ghostty.py`** — ONLY patches `~/.config/ghostty/config` and
  sends `SIGUSR2` to running Ghostty processes. Owns the
  `SOLARIS_THEME_START/END` marker block in the Ghostty config format.
- **`solaris/solar.py`** — ONLY does solar math via `astral`. Reads the system
  clock and `/etc/localtime` / `/etc/timezone`; nothing else.
- **`solaris/systemd_manager.py`** — ONLY generates/queries systemd user units
  (`solaris-update.{service,timer}` and `solaris-watcher.service`). Wraps
  `systemctl --user` calls.
- **`solaris/watcher.py`** — ONLY listens to GSettings and applies the theme
  stack. The **one** module allowed to use `Gio.Settings` directly (it reads
  the system `org.gnome.desktop.interface` schema, not the optional
  user-theme schema). Designed to be invoked by `solaris-watcher.service`.
- **`solaris/cli.py`** — Orchestrates the above modules. This is the "glue."
  Has one handler per CLI flag. Imports `firefox`, `ghostty`,
  `systemd_manager`, `theme_engine`, `solar`, `watcher`.
- **`solaris/app.py`** + **`solaris/ui/`** — GUI layer. Calls the same core
  modules as CLI. `ui/status_page.py` shows the dashboard; `ui/preferences_page.py`
  exposes settings.

> Modules must NEVER import each other horizontally (e.g., `theme_engine`
> must not import `firefox` or `ghostty`). All coordination happens in
> `cli.py`, `app.py`, or `watcher.py`.

## Schedule Modes
The CLI and timer logic all branch on `cfg.schedule_mode`:
- `solar` (default) — switch at local sunrise/sunset; timer self-reschedules
  for tomorrow on every fire.
- `time` — switch at fixed `cfg.time_light_start` / `cfg.time_dark_start`
  (24-hour HH:MM); timer uses two stable `OnCalendar` lines.
- `manual` — always apply `cfg.manual_mode`; no timer is needed.

`SolarisConfig.__post_init__` validates `latitude`, `longitude`, `schedule_mode`,
the two HH:MM strings, and `ghostty_window_decoration`.

## Safety Guardrails (Critical)
- Never write to system-wide paths (`/usr/share/`, `/etc/`) — only user paths
  under `$HOME`. `install.sh` is allowed to read `/etc/os-release` only.
- Never delete files without explicit user confirmation.
- Never commit config files containing user coordinates, paths, or
  `~/.config/solaris/config.json`.
- Every `subprocess.run()` call is checked: log `stderr` and return
  gracefully on non-zero `returncode`. The systemd manager logs and
  returns `False` from `_run_systemctl` rather than raising.
- `SolarisConfig.__post_init__` validates latitude (-90 to 90) and
  longitude (-180 to 180) before the config ever reaches `astral`.
- Firefox **and** Ghostty patchers must create a `.bak` backup of the
  target file before any modification.
- Firefox / Ghostty patchers must only modify content between the
  `SOLARIS_THEME_START` / `SOLARIS_THEME_END` markers; if absent,
  append a default block.
- Systemd unit operations must call `daemon-reload` after file changes
  (`systemd_manager.update_timer` and `install_watcher_service` do this).
- The `watcher` service uses SIGTERM (systemd) and SIGINT handlers to
  exit cleanly; do not add threads to `solaris/watcher.py`.

## Architecture Rules
- All config lives in `~/.config/solaris/config.json` (via `pyxdg`).
- All systemd units live in `~/.config/systemd/user/`.
- gsettings commands use `subprocess.run`, **NOT** `Gio.Settings` —
  the single documented exception is `solaris/watcher.py` reading the
  always-present `org.gnome.desktop.interface color-scheme` key.
- The systemd service `ExecStart` is `solaris --auto` (via
  `python -m solaris.cli --auto`), which applies the theme AND
  rewrites the timer for the next transition — the "self-rescheduling"
  pattern. No long-running daemon is needed for the timer.
- The optional `solaris-watcher.service` IS long-running; it blocks on
  a `GLib.MainLoop` listening to the `color-scheme` GSettings signal.
- GUI and CLI are equal citizens — both call into the same core library
  (`config`, `theme_engine`, `firefox`, `ghostty`, `solar`,
  `systemd_manager`).
- `install.sh` is a single-file bash script with helper functions
  (`detect_distro`, `pkg_manager`, `pkg_install_cmd`, `check_runtime_deps`).
  It does NOT run `sudo`; it only tells the user what to install.
- The desktop entry lives at `~/.local/share/applications/solaris.desktop`
  and the hicolor icon set at `~/.local/share/icons/hicolor/{size}/apps/`.

## Git Conventions
- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`.
- PR titles must be under 72 characters.
- Keep PRs under 400 lines of diff when possible.
- Never commit `uv.lock` or `PRD.md` — both are in `.gitignore`.

## Communication
- Be concise — skip explanations of basic concepts.
- When suggesting a change, explain the 'why', not just the 'what'.
- If you notice a potential bug while working on something else, stop and flag it.
- Always suggest the simplest solution that meets the requirements.
- When uncertain about intent, ask rather than guess.
