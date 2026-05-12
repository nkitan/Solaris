# AGENTS.md — Project Rules for AI Coding Agents
# This file is read by Antigravity (v1.20.3+), Cursor, and Claude Code.
# Rules here apply to all tools. Antigravity-specific overrides go in GEMINI.md.

## Project Overview
- **Name:** Solaris
- **Type:** GNOME-native desktop application (GTK4 GUI + CLI)
- **Stage:** Active Development (MVP)
- **Purpose:** Solar-aware theme orchestration for Arch Linux — automatically switches GTK/Shell themes and Firefox CSS at sunrise/sunset using systemd user timers.

## Tech Stack
- **Language:** Python 3.13+ (strict typing with `from __future__ import annotations`)
- **Package Manager:** uv
- **GUI Framework:** PyGObject (gi) with Libadwaita (GTK4)
- **Key Libraries:** astral (solar calculations), pyxdg (XDG paths)
- **System Integration:** gsettings (dconf), systemd user units, Firefox userChrome.css
- **Testing:** pytest
- **Target OS:** Arch Linux running GNOME 46+

## Code Quality
- Maximum file length: 300 lines — split larger files into modules
- Maximum function length: 30 lines
- No `print()` in library code — use Python `logging` module
- CLI and GUI entry points are the only places that configure log handlers
- Use `@dataclass` for structured data, `NamedTuple` for immutable records
- All public functions and classes must have docstrings (Google style)
- Type hints on all function signatures — no `Any` unless absolutely necessary
- Prefer `Path` objects over string paths
- Use `subprocess.run()` with `capture_output=True, text=True, check=False` for shell commands

## Module Boundaries (Critical)
- **`solaris/config.py`** — ONLY reads/writes JSON config. No gsettings, no subprocess.
- **`solaris/theme_engine.py`** — ONLY interacts with gsettings. Receives config values as parameters.
- **`solaris/firefox.py`** — ONLY patches userChrome.css. No gsettings interaction.
- **`solaris/solar.py`** — ONLY does solar math. No I/O except reading system clock.
- **`solaris/systemd_manager.py`** — ONLY generates/manages systemd unit files.
- **`solaris/cli.py`** — Orchestrates the above modules. This is the "glue."
- **`solaris/app.py`** + **`solaris/ui/`** — GUI layer. Calls the same core modules as CLI.

> Modules must NEVER import each other horizontally (e.g., `theme_engine` must not import `firefox`).
> All coordination happens in `cli.py` or `app.py`.

## Safety Guardrails (Critical)
- Never write to system-wide paths (`/usr/share/`, `/etc/`) — only user paths
- Never delete files without explicit user confirmation
- Never commit config files containing user coordinates or paths
- Wrap all `subprocess.run()` calls in try/except with proper error logging
- Validate latitude/longitude ranges before passing to astral (-90 to 90, -180 to 180)
- Firefox patcher must create backups before modifying userChrome.css
- Systemd unit operations must call `daemon-reload` after file changes

## Git Conventions
- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- PR titles must be under 72 characters
- Keep PRs under 400 lines of diff when possible

## Architecture Rules
- All config lives in `~/.config/solaris/` (via `pyxdg`)
- All systemd units live in `~/.config/systemd/user/`
- gsettings commands use `subprocess.run`, NOT `Gio.Settings` (for User Themes extension compatibility)
- The systemd service calls `solaris --auto` which self-reschedules the timer
- GUI and CLI are equal citizens — both use the same core library

## Communication
- Be concise — skip explanations of basic concepts
- When suggesting a change, explain the 'why', not just the 'what'
- If you notice a potential bug while working on something else, stop and flag it
- Always suggest the simplest solution that meets the requirements
- When uncertain about intent, ask rather than guess