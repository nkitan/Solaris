"""Solaris CLI entry point.

Exposes headless, non-GUI operations so that the systemd service units
and shell scripts can drive Solaris without launching a GUI.

Usage examples:
  solaris --status
  solaris --apply-light
  solaris --apply-dark
  solaris --auto
  solaris --install-timer
  solaris --update-timer
  solaris --watch
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from solaris import __version__
from solaris import config as config_module
from solaris import firefox, ghostty, systemd_manager, theme_engine
from solaris.solar import SolarCalculator
from solaris.watcher import DarkStyleWatcher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _configure_logging(verbose: bool = False) -> None:
    """Set up root logger to write to stderr with a simple format."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _handle_apply_light(cfg: config_module.SolarisConfig) -> None:
    """Force-apply the light theme and patch Firefox/Ghostty."""
    theme_engine.apply_light(cfg)
    if cfg.firefox_integration:
        firefox.apply_theme("light")
    if cfg.ghostty_integration:
        ghostty.apply_theme("light", cfg)
    print("✓ Light theme applied.")


def _handle_apply_dark(cfg: config_module.SolarisConfig) -> None:
    """Force-apply the dark theme and patch Firefox/Ghostty."""
    theme_engine.apply_dark(cfg)
    if cfg.firefox_integration:
        firefox.apply_theme("dark")
    if cfg.ghostty_integration:
        ghostty.apply_theme("dark", cfg)
    print("✓ Dark theme applied.")


def _determine_time_mode(cfg: config_module.SolarisConfig) -> str:
    """Determine light/dark based on current time vs. the configured HH:MM window.

    Returns "light" if the current local time is inside the window
    [time_light_start, time_dark_start), "dark" otherwise.

    Args:
        cfg: The loaded SolarisConfig.

    Returns:
        "light" or "dark".
    """
    import datetime

    def _parse_hhmm(hhmm: str) -> datetime.time:
        h, m = hhmm.split(":")
        return datetime.time(int(h), int(m))

    now_time = datetime.datetime.now().time()
    light_start = _parse_hhmm(cfg.time_light_start)
    dark_start = _parse_hhmm(cfg.time_dark_start)

    if light_start < dark_start:
        # Normal case: light window is e.g. 07:00–20:00
        return "light" if light_start <= now_time < dark_start else "dark"
    else:
        # Inverted window crosses midnight: dark window spans midnight
        return "dark" if dark_start <= now_time < light_start else "light"


def _handle_auto(cfg: config_module.SolarisConfig) -> None:
    """Apply the theme for the current schedule mode, then reschedule the timer.

    This is the function called by the systemd service unit on each transition.
    Behaviour depends on cfg.schedule_mode:

    - "solar"  — calculate mode from local sunrise/sunset, reschedule for tomorrow.
    - "manual" — always apply cfg.manual_mode; no timer rescheduling needed.
    - "time"   — calculate mode from HH:MM window; rewrite timer with fixed times.
    """
    import datetime

    schedule_mode = cfg.schedule_mode
    logger.info("--auto: schedule_mode=%s", schedule_mode)

    if schedule_mode == config_module.SCHEDULE_MODE_MANUAL:
        mode = cfg.manual_mode
        logger.info("Manual mode: applying %s", mode)

    elif schedule_mode == config_module.SCHEDULE_MODE_TIME:
        mode = _determine_time_mode(cfg)
        logger.info("Time-based mode: current mode=%s", mode)
        # Rewrite timer with the fixed times (idempotent — safe to repeat).
        try:
            systemd_manager.update_timer_time_based(
                cfg.time_light_start, cfg.time_dark_start
            )
        except Exception as exc:
            logger.error("Failed to update time-based timer: %s", exc)

    else:  # SCHEDULE_MODE_SOLAR (default)
        calculator = SolarCalculator(cfg.latitude, cfg.longitude)
        mode = calculator.get_current_mode()
        logger.info("Solar mode: current mode=%s", mode)
        # Reschedule the timer for tomorrow's solar transitions.
        tomorrow = date.today() + datetime.timedelta(days=1)
        try:
            tomorrow_times = calculator.get_times(tomorrow)
            systemd_manager.update_timer(tomorrow_times.sunrise, tomorrow_times.sunset)
            logger.info("Solar timer updated for %s.", tomorrow)
        except Exception as exc:
            logger.error("Failed to update solar timer: %s", exc)

    if mode == "light":
        _handle_apply_light(cfg)
    else:
        _handle_apply_dark(cfg)


def _handle_status(cfg: config_module.SolarisConfig) -> None:
    """Print current mode, next transition, and timer status."""
    current_mode = theme_engine.get_current_mode()
    timer_active = systemd_manager.is_active()
    timer_enabled = systemd_manager.is_enabled()
    watcher_active = systemd_manager.is_watcher_active()
    watcher_enabled = systemd_manager.is_watcher_enabled()

    print(f"Solaris v{__version__}")
    print(f"  Current mode      : {current_mode}")
    print(f"  Schedule mode     : {cfg.schedule_mode}")

    if cfg.schedule_mode == config_module.SCHEDULE_MODE_SOLAR:
        calculator = SolarCalculator(cfg.latitude, cfg.longitude)
        countdown = calculator.format_countdown()
        print(f"  Next transition   : {countdown}")
        print(f"  Location          : {cfg.latitude}°N, {cfg.longitude}°E")
    elif cfg.schedule_mode == config_module.SCHEDULE_MODE_MANUAL:
        print(f"  Manual mode       : {cfg.manual_mode}")
    elif cfg.schedule_mode == config_module.SCHEDULE_MODE_TIME:
        print(f"  Light window      : {cfg.time_light_start} – {cfg.time_dark_start}")

    print(f"  Timer active      : {'yes' if timer_active else 'no'}")
    print(f"  Timer enabled     : {'yes' if timer_enabled else 'no'}")
    print(f"  Dark Style watcher: {'active ✅' if watcher_active else 'inactive'}")
    print(f"  Watcher enabled   : {'yes' if watcher_enabled else 'no'}")
    print(f"  Follow Dark Style : {'yes' if cfg.follow_dark_style else 'no'}")


def _handle_install_timer(cfg: config_module.SolarisConfig) -> None:
    """Generate and install the systemd service and timer units, then enable them."""
    if cfg.schedule_mode == config_module.SCHEDULE_MODE_TIME:
        # Time-based: write fixed OnCalendar entries.
        UNIT_DIR = systemd_manager.UNIT_DIR
        UNIT_DIR.mkdir(parents=True, exist_ok=True)
        service_path = UNIT_DIR / systemd_manager.SERVICE_NAME
        service_content = systemd_manager._SERVICE_TEMPLATE.format(python_path=sys.executable)
        service_path.write_text(service_content, encoding="utf-8")
        systemd_manager.update_timer_time_based(
            cfg.time_light_start, cfg.time_dark_start
        )
        systemd_manager.enable()
        print("\u2713 Solaris systemd timer installed and enabled (time-based).")
        print(f"  Light at: {cfg.time_light_start}")
        print(f"  Dark at : {cfg.time_dark_start}")
    elif cfg.schedule_mode == config_module.SCHEDULE_MODE_MANUAL:
        print("ℹ️  Manual mode active — no timer needed.")
    else:
        # Solar mode: calculate today's times.
        calculator = SolarCalculator(cfg.latitude, cfg.longitude)
        try:
            today_times = calculator.get_times()
        except Exception as exc:
            print(f"\u2717 Failed to calculate solar times: {exc}", file=sys.stderr)
            sys.exit(1)
        systemd_manager.install_units(today_times.sunrise, today_times.sunset)
        systemd_manager.enable()
        print("\u2713 Solaris systemd timer installed and enabled (solar).")
        print(f"  Sunrise: {today_times.sunrise.strftime('%H:%M %Z')}")
        print(f"  Sunset : {today_times.sunset.strftime('%H:%M %Z')}")


def _handle_update_timer(cfg: config_module.SolarisConfig) -> None:
    """Recalculate or reconfirm timer schedule based on the active schedule mode."""
    if cfg.schedule_mode == config_module.SCHEDULE_MODE_TIME:
        systemd_manager.update_timer_time_based(
            cfg.time_light_start, cfg.time_dark_start
        )
        print("\u2713 Solaris timer updated (time-based).")
        print(f"  Light at: {cfg.time_light_start}")
        print(f"  Dark at : {cfg.time_dark_start}")
    elif cfg.schedule_mode == config_module.SCHEDULE_MODE_MANUAL:
        print("ℹ️  Manual mode active — no timer to update.")
    else:
        calculator = SolarCalculator(cfg.latitude, cfg.longitude)
        try:
            today_times = calculator.get_times()
        except Exception as exc:
            print(f"\u2717 Failed to calculate solar times: {exc}", file=sys.stderr)
            sys.exit(1)
        systemd_manager.update_timer(today_times.sunrise, today_times.sunset)
        print("\u2713 Solaris timer updated (solar).")
        print(f"  Sunrise: {today_times.sunrise.strftime('%H:%M %Z')}")
        print(f"  Sunset : {today_times.sunset.strftime('%H:%M %Z')}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="solaris",
        description="Solar-aware GNOME theme orchestrator for Arch Linux.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  solaris --status           Show current mode and next transition
  solaris --apply-light      Force light theme
  solaris --apply-dark       Force dark theme
  solaris --auto             Apply theme based on solar position (used by systemd)
  solaris --install-timer    Install and enable the systemd timer
  solaris --update-timer     Recalculate and update the timer schedule
""",
    )

    parser.add_argument(
        "--version", action="version", version=f"solaris {__version__}"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--apply-light",
        action="store_true",
        help="Force-apply the light theme and patch Firefox.",
    )
    group.add_argument(
        "--apply-dark",
        action="store_true",
        help="Force-apply the dark theme and patch Firefox.",
    )
    group.add_argument(
        "--auto",
        action="store_true",
        help="Apply the theme for the current solar position, then reschedule the timer.",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Print current mode, next transition, and timer status.",
    )
    group.add_argument(
        "--install-timer",
        action="store_true",
        help="Generate and enable the systemd service and timer units.",
    )
    group.add_argument(
        "--update-timer",
        action="store_true",
        help="Recalculate solar times and rewrite the timer unit.",
    )
    group.add_argument(
        "--watch",
        action="store_true",
        help=(
            "Start the Dark Style watcher: block and sync themes whenever the "
            "GNOME color-scheme GSettings key changes. Used by solaris-watcher.service."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _handle_watch() -> None:
    """Start the blocking Dark Style watcher loop.

    Called by solaris-watcher.service via `solaris --watch`.
    Applies the current color-scheme theme immediately on startup,
    then blocks until SIGTERM or SIGINT is received.
    """
    logger.info("Starting Dark Style watcher.")
    watcher = DarkStyleWatcher()
    watcher.start()  # blocks until signal


def main() -> None:
    """CLI entry point called by the `solaris` console script."""
    parser = _build_parser()
    args = parser.parse_args()

    _configure_logging(verbose=args.verbose)

    cfg = config_module.load()

    if args.apply_light:
        _handle_apply_light(cfg)
    elif args.apply_dark:
        _handle_apply_dark(cfg)
    elif args.auto:
        _handle_auto(cfg)
    elif args.status:
        _handle_status(cfg)
    elif args.install_timer:
        _handle_install_timer(cfg)
    elif args.update_timer:
        _handle_update_timer(cfg)
    elif args.watch:
        _handle_watch()


if __name__ == "__main__":
    main()
