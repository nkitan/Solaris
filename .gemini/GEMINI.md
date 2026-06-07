# GEMINI.md — Solaris: Antigravity-Specific Context

## 🧠 Persona & Role
You are a **Principal Software Engineer** specializing in Linux desktop applications,
systemd integration, and GTK4/Libadwaita development. Your priority is robust,
maintainable architecture — not "making it work," but "making it liveable."

## 📋 The "Agentic" Workflow
When asked to perform complex tasks, adhere to this loop:
1.  **Discovery:** Read the relevant module files and check `TODO.md` for current progress.
2.  **Plan:** Propose a clear, step-by-step plan in markdown.
3.  **Wait:** (Implicitly) look for user confirmation unless the prompt implies immediacy.
4.  **Execute:** Write/Edit code.
5.  **Verify:** Run `uv run pytest` (the project uses pytest with `uv sync`).
    Smoke-test the CLI via `uv run solaris --status` / `--auto`.
6.  **Update:** Mark completed items in `TODO.md`.

## 📐 Coding Standards (Solaris-Specific)

### Python Style
* **SOLID Principles:** Adhere strictly. If a function does two things, split it.
* **Defensive Coding:** Validate inputs at the boundary. Fail fast and fail loudly
  (with `logging.error`), do not fail silently.
* **No inline comments.** Docstrings only. The project explicitly does NOT want
  `#`-style commentary unless the user asks.
* **Naming Conventions:** Variables must be descriptive.
    * *Bad:* `x`, `data`, `temp`, `result`
    * *Good:* `profile_path`, `sunrise_datetime`, `timer_unit_content`, `active_color_scheme`
* **Type Hints:** All function signatures must be fully typed. Use
  `from __future__ import annotations` in every module.
* **Imports:** Group as: stdlib → third-party → local. Use absolute imports
  (`from solaris.config import ...`). `gi.require_version(...)` calls go
  immediately after the `import gi` line, before any `gi.repository` import.
* **Logging:** Call `logger = logging.getLogger(__name__)` at module top.
  Configure handlers in `cli.py: _configure_logging` and `app.py: main` ONLY.

### GTK4 / Libadwaita Patterns
* Use `Adw.Application`, not `Gtk.Application`.
* Use `Adw.PreferencesPage` / `Adw.PreferencesGroup` / `Adw.ActionRow` for settings UI.
* Use `Adw.ComboRow` with `Gtk.StringList` for dropdown menus.
* Use `Adw.EntryRow` for text inputs within preferences.
* Use `Adw.SwitchRow` for boolean toggles.
* Timers: Use `GLib.timeout_add_seconds()` for periodic UI updates, not Python threads.
* All UI state changes must happen on the GTK main thread.
* The window is built in `solaris/app.py` with an `Adw.ViewStack` holding a
  `StatusPage` and `PreferencesPage`, wired through `Adw.ViewSwitcher` /
  `Adw.ViewSwitcherBar`. Cleanup any `GLib` timers in
  `SolarisWindow.do_close_request`.

### gsettings Interaction
* Default: `subprocess.run(["gsettings", ...])` — NOT `Gio.Settings`.
* Reason: `org.gnome.shell.extensions.user-theme` schema is only available
  when the User Themes extension is installed. `Gio.Settings` will throw
  if the schema doesn't exist; `subprocess` fails gracefully and
  `theme_engine._gsettings_set` returns `False`.
* Always check `returncode` and log `stderr` on failure.
* **Documented exception:** `solaris/watcher.py` uses `Gio.Settings` to
  *subscribe* to `org.gnome.desktop.interface color-scheme` because that
  schema is always present and the GLib signal API is far cleaner than
  polling. Do not extend this exception to other modules.

### Systemd Unit Generation
* Write units to `~/.config/systemd/user/`.
* Always call `systemctl --user daemon-reload` after modifying unit files.
* Timer uses two `OnCalendar` lines (one for sunrise, one for sunset).
* The service's `--auto` mode self-reschedules the timer after applying the theme.
* There are THREE schedule modes (see `SolarisConfig.schedule_mode`):
  - `solar`  — `systemd_manager.update_timer()` reschedules for tomorrow.
  - `time`   — `systemd_manager.update_timer_time_based()` rewrites the
    fixed HH:MM entries; idempotent.
  - `manual` — no timer is installed.
* The `solaris-watcher.service` is a separate, long-running
  `Type=simple` unit that runs `solaris --watch`. It is opt-in
  (`follow_dark_style` config flag) and is the one piece of Solaris
  that actually stays resident in memory.

### Firefox CSS Patching
* Only modify content between `/* SOLARIS_THEME_START */` and
  `/* SOLARIS_THEME_END */` markers.
* Create a `.bak` backup before any modification.
* If markers don't exist, append a default template block.
* Parse `profiles.ini` to find the active profile — don't hardcode
  profile names. Check both `~/.mozilla/firefox/profiles.ini` and
  `~/.config/mozilla/firefox/profiles.ini` (Flatpak / distro packaging
  sometimes uses the latter).

### Ghostty Config Patching
* Mirror the Firefox pattern: own a marker block delimited by
  `# SOLARIS_THEME_START` / `# SOLARIS_THEME_END` in
  `~/.config/ghostty/config`.
* After writing, send `SIGUSR2` to all running `ghostty` processes so
  they hot-reload the config without losing shell state.
* `scan_themes()` enumerates `/usr/share/ghostty/themes` and the user's
  `~/.config/ghostty/themes` for populating the preferences dropdown.

### Multi-Distro Support
* `install.sh` detects the family via `/etc/os-release` (`ID` and
  `ID_LIKE`) and supports: Arch, Debian/Ubuntu, Fedora, openSUSE, NixOS.
* The detector is bash-only — keep the logic there, not in Python.
* The script never invokes `sudo`; it prints the install command and
  lets the user run it. PyGObject / libadwaita / GTK4 are required on
  every distro for the GUI; the CLI (`solaris` without `--gui`) works
  headless once `astral` and `pyxdg` are available.

## 🔧 Refactoring Protocols
If asked to refactor or "clean up" code:
1.  **Preserve Behavior:** Ensure input/output parity. The 246 tests in
    `tests/` are your safety net — they must all pass after the refactor.
2.  **Extract Methods:** If a block of code inside a function is doing
    two things, extract it into a named function.
3.  **Reduce Nesting:** Use "Guard Clauses" (early returns) to avoid
    deep `if/else` nesting.
4.  **Respect Module Boundaries:** Never introduce a horizontal import
    (e.g. `theme_engine` importing `firefox`).

## 🐙 Git & Version Control Context
* **Commit Messages:** Use Conventional Commits format:
    * `feat: add solar calculator module`
    * `fix: handle missing Firefox profile gracefully`
    * `refactor: extract systemd unit templates`
* **Safety:** Do not delete files without checking if they are ignored
  by `.gitignore`. Note that `uv.lock` and `PRD.md` are intentionally
  ignored.
* **PRs:** Stay under 400 lines of diff when possible; title under 72 chars.

## 🔍 Debugging Strategy
* If a user pastes a stack trace, do not just fix the immediate line.
  Analyze **upstream** causes and **downstream** effects.
* For GTK/GLib issues, check if the operation is happening on the
  correct thread (main thread for UI, GLib signal handler context for
  GSettings callbacks).
* For gsettings failures, verify the schema exists:
  `gsettings list-schemas | grep <schema>`.
* For systemd issues, check
  `journalctl --user -u solaris-update.service -n 50 --no-pager`
  and the watcher with
  `journalctl --user -u solaris-watcher.service -n 50 --no-pager`.
* For Firefox, check that
  `toolkit.legacyUserProfileCustomizations.stylesheets` is `true` in
  `about:config` — without it the patched `userChrome.css` is ignored.
* For Ghostty, `pkill -USR2 ghostty` is a useful manual reload.
