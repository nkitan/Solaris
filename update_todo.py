import re

with open('/home/notroot/Work/Solaris/TODO.md', 'r') as f:
    lines = f.readlines()

completed_items = [
    "Update `pyproject.toml`",
    "Create `solaris/__init__.py`",
    "Delete placeholder `main.py`",
    "Verify `uv run solaris --help`",
    "Create `solaris/config.py`",
    "Implement `load()`",
    "Implement `save()`",
    "Use `pyxdg`",
    "Implement `apply_light()`",
    "Implement `apply_dark()`",
    "Implement `get_current_mode()`",
    "Implement `scan_themes()`",
    "Gracefully handle missing User Themes",
    "Implement `find_active_profile()`",
    "Implement `apply_theme()`",
    "Handle `SOLARIS_THEME_START`",
    "Append default template",
    "Implement `ensure_user_chrome_dir()`",
    "Return `False`",
    "Implement `SolarCalculator.__init__()`",
    "Implement `get_times()`",
    "next_transition()",
    "Define service unit template",
    "Define timer unit template",
    "Implement `install_units()`",
    "Implement `update_timer()`",
    "Implement `enable()`",
    "Set up `argparse`",
    "Implement `--apply-light` handler",
    "Implement `--apply-dark` handler",
    "Implement `--auto` handler",
    "Implement `--status` handler",
    "Implement `--install-timer` handler",
    "Implement `--update-timer` handler",
    "Verify `uv run solaris --status` works",
    "Create `Adw.Application` subclass",
    "Set up `Adw.ApplicationWindow`",
    "Add view switching",
    "Wire up application activation",
    "Create `Adw.StatusPage`",
    "Add Override toggle",
    "Add \"Next Transition\" countdown row",
    "Add \"Apply Now\" button",
    "Add systemd timer status row",
    "Wire all widgets",
    "Create Theme preferences group",
    "Populate dropdowns",
    "Create Location preferences group",
    "Add \"Detect Location\" button",
    "Create Firefox preferences group",
    "Update `README.md`",
    "Update `.gitignore`",
    "`uv run solaris --install-timer`"
]

new_lines = []
for line in lines:
    marked = False
    for item in completed_items:
        if item in line and "- [ ]" in line:
            new_lines.append(line.replace("- [ ]", "- [x]"))
            marked = True
            break
    
    if not marked:
        # Also handle get_current_mode for solar.py which has the same name
        if "- [ ] Implement `get_current_mode()`" in line:
             new_lines.append(line.replace("- [ ]", "- [x]"))
        else:
            new_lines.append(line)

with open('/home/notroot/Work/Solaris/TODO.md', 'w') as f:
    f.writelines(new_lines)
