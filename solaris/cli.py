"""Solaris CLI entry point.

Exposes headless, non-GUI operations so that the systemd service unit
and shell scripts can drive Solaris without launching a GUI.

Usage examples:
  solaris --status
  solaris --apply-light
  solaris --apply-dark
  solaris --auto
  solaris --install-timer
  solaris --update-timer
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from solaris import __version__
from solaris import config as config_module
from solaris import firefox, systemd_manager, theme_engine
from solaris.solar import SolarCalculator

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
    """Force-apply the light theme and patch Firefox."""
    theme_engine.apply_light(cfg)
    if cfg.firefox_integration:
        firefox.apply_theme("light")
    print("✓ Light theme applied.")


def _handle_apply_dark(cfg: config_module.SolarisConfig) -> None:
    """Force-apply the dark theme and patch Firefox."""
    theme_engine.apply_dark(cfg)
    if cfg.firefox_integration:
        firefox.apply_theme("dark")
    print("✓ Dark theme applied.")


def _handle_auto(cfg: config_module.SolarisConfig) -> None:
    """Apply the theme appropriate for the current solar position, then reschedule the timer.

    This is the function called by the systemd service unit on each transition.
    After applying the theme it updates the timer to fire at tomorrow's
    sunrise/sunset, keeping the schedule self-maintaining.
    """
    calculator = SolarCalculator(cfg.latitude, cfg.longitude)

    if cfg.override_mode is not None:
        mode = cfg.override_mode
        logger.info("Override mode active: %s", mode)
    else:
        mode = calculator.get_current_mode()
        logger.info("Solar mode determined: %s", mode)

    if mode == "light":
        _handle_apply_light(cfg)
    else:
        _handle_apply_dark(cfg)

    # Reschedule the timer for tomorrow's transitions.
    import datetime
    tomorrow = date.today() + datetime.timedelta(days=1)
    try:
        tomorrow_times = calculator.get_times(tomorrow)
        systemd_manager.update_timer(tomorrow_times.sunrise, tomorrow_times.sunset)
        logger.info("Timer updated for tomorrow: %s", tomorrow)
    except Exception as exc:
        logger.error("Failed to update timer after auto-apply: %s", exc)


def _handle_status(cfg: config_module.SolarisConfig) -> None:
    """Print current mode, next transition, and timer status."""
    current_mode = theme_engine.get_current_mode()
    timer_active = systemd_manager.is_active()
    timer_enabled = systemd_manager.is_enabled()

    calculator = SolarCalculator(cfg.latitude, cfg.longitude)
    countdown = calculator.format_countdown()

    print(f"Solaris v{__version__}")
    print(f"  Current mode   : {current_mode}")
    print(f"  Override mode  : {cfg.override_mode or 'none (auto)'}")
    print(f"  Next transition: {countdown}")
    print(f"  Location       : {cfg.latitude}°N, {cfg.longitude}°E")
    print(f"  Timer active   : {'yes' if timer_active else 'no'}")
    print(f"  Timer enabled  : {'yes' if timer_enabled else 'no'}")


def _handle_install_timer(cfg: config_module.SolarisConfig) -> None:
    """Generate and install the systemd service and timer units, then enable them."""
    calculator = SolarCalculator(cfg.latitude, cfg.longitude)

    try:
        today_times = calculator.get_times()
    except Exception as exc:
        print(f"✗ Failed to calculate solar times: {exc}", file=sys.stderr)
        sys.exit(1)

    systemd_manager.install_units(today_times.sunrise, today_times.sunset)
    systemd_manager.enable()
    print("✓ Solaris systemd timer installed and enabled.")
    print(f"  Sunrise: {today_times.sunrise.strftime('%H:%M %Z')}")
    print(f"  Sunset : {today_times.sunset.strftime('%H:%M %Z')}")


def _handle_update_timer(cfg: config_module.SolarisConfig) -> None:
    """Recalculate today's solar times and rewrite the timer unit."""
    calculator = SolarCalculator(cfg.latitude, cfg.longitude)

    try:
        today_times = calculator.get_times()
    except Exception as exc:
        print(f"✗ Failed to calculate solar times: {exc}", file=sys.stderr)
        sys.exit(1)

    systemd_manager.update_timer(today_times.sunrise, today_times.sunset)
    print("✓ Solaris timer updated.")
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

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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


if __name__ == "__main__":
    main()
