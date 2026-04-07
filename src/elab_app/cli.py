"""cli.py — Command-line entry point for elab-app.

Commands:
    elab-app start              Launch the Streamlit interface
    elab-app config show        Print current configuration
    elab-app config set KEY VAL Write a key=value to the config file
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Optional

import typer
from platformdirs import user_config_dir

app = typer.Typer(help="elab-app — ElabFTW Logger")

_CONFIG_DIR = Path(user_config_dir("elab_app"))
_CONFIG_FILE = _CONFIG_DIR / "config.toml"
_DEFAULT_HOST = "https://eln.ub.tum.de/api/v2"


def _load_config() -> dict:
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    return {"elab_host": _DEFAULT_HOST}


def _save_config(config: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        for k, v in config.items():
            f.write(f'{k} = "{v}"\n')


@app.command()
def start():
    """Launch the elab-app Streamlit interface."""
    package_dir = Path(__file__).parent

    # Copy default templates to user config dir if not present
    user_templates = _CONFIG_DIR / "templates"
    pkg_templates = package_dir / "templates"
    if pkg_templates.exists() and not user_templates.exists():
        shutil.copytree(pkg_templates, user_templates)

    # Ensure keys dir exists
    (_CONFIG_DIR / "keys").mkdir(parents=True, exist_ok=True)

    main_py = package_dir / "main.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(main_py)],
        cwd=str(package_dir),
    )


def _show_config() -> None:
    cfg = _load_config()

    typer.echo("=== Settings ===")
    typer.echo(f"  Config file : {_CONFIG_FILE}")
    for k, v in cfg.items():
        typer.echo(f"  {k} = {v}")

    typer.echo("\n=== Users (encrypted key files) ===")
    keys_dir = _CONFIG_DIR / "keys"
    typer.echo(f"  Directory   : {keys_dir}")
    if keys_dir.exists():
        users = sorted(p.stem for p in keys_dir.glob("*.enc"))
        if users:
            for u in users:
                typer.echo(f"  {u}")
        else:
            typer.echo("  (none)")
    else:
        typer.echo("  (directory not created yet)")

    typer.echo("\n=== Templates ===")
    templates_dir = _CONFIG_DIR / "templates"
    typer.echo(f"  Directory   : {templates_dir}")
    if templates_dir.exists():
        yamls = sorted(p.name for p in templates_dir.glob("*.yaml"))
        if yamls:
            for t in yamls:
                typer.echo(f"  {t}")
        else:
            typer.echo("  (none)")
    else:
        typer.echo("  (directory not created yet — run 'elab-app start' once to populate)")


@app.command()
def config(
    action: Optional[str] = typer.Argument(default=None, help="show (default) | set"),
    key: Optional[str] = typer.Argument(default=None),
    value: Optional[str] = typer.Argument(default=None),
):
    """Show configuration or set a value.

    Run with no arguments (or 'show') to print all settings, users, and templates.

    Examples:\n
        elab-app config\n
        elab-app config show\n
        elab-app config set elab_host https://your-instance.example.com/api/v2
    """
    if action is None or action == "show":
        _show_config()
    elif action == "set":
        if not key or value is None:
            typer.echo("Usage: elab-app config set <key> <value>", err=True)
            raise typer.Exit(1)
        cfg = _load_config()
        cfg[key] = value
        _save_config(cfg)
        typer.echo(f"Set {key} = {value}")
    else:
        typer.echo(f"Unknown action '{action}'. Use 'show' or 'set'.", err=True)
        raise typer.Exit(1)
