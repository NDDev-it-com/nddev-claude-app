#!/usr/bin/env python3
"""NDDev Claude Code setup manager.

Installs, updates, switches, and removes a selected NDDev marketplace of Claude
Code plugins in a caller-selected Claude Code home (an explicit ``--target``
directory, never an inferred ``~/.claude``). The manager owns *only* two keys in
the target's ``settings.json`` -- its marketplace entry under
``extraKnownMarketplaces`` and its plugin-enable flags under ``enabledPlugins``
-- plus its own stamp file. Every other settings key, ``.credentials.json``,
``projects/``, and the Claude-CLI-owned ``plugins/`` registry are preserved
verbatim. Mutations are atomic (temp + rename), backed up to a target-bound
slot, and rolled back on failure.

Dependency-free; standard library only; Python >= 3.10.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parent.parent
PRODUCT_NAME = "nddev-claude-app"
STAMP_NAME = "NDDEV-CLAUDE-SETUP.json"
STAMP_SCHEMA = 1
SETTINGS_NAME = "settings.json"
CATALOG_ROOT = ROOT / "setups"
MAX_BACKUPS = 10
OWNER_FILE_MODE = 0o600
OWNER_DIR_MODE = 0o700
MANAGED_PAYLOAD_MAX_BYTES = 4 * 1024 * 1024

# The two settings.json keys this manager owns. Everything else in settings.json
# is a sibling overlay preserved verbatim.
MARKETPLACES_KEY = "extraKnownMarketplaces"
ENABLED_PLUGINS_KEY = "enabledPlugins"


class ManagerError(Exception):
    """A structured, user-facing manager failure."""


def fail(message: str) -> NoReturn:
    raise ManagerError(message)


# --- catalog ---------------------------------------------------------------


@dataclass(frozen=True)
class Setup:
    setup_id: str
    description: str
    marketplace_name: str
    marketplace_source: dict[str, Any]
    auto_update: bool
    plugins: tuple[str, ...]

    @property
    def enable_keys(self) -> tuple[str, ...]:
        return tuple(f"{plugin}@{self.marketplace_name}" for plugin in self.plugins)


def _validate_setup_id(setup_id: str) -> None:
    if not setup_id or not all(ch.isalnum() or ch in "-_" for ch in setup_id):
        fail(f"invalid setup id: {setup_id!r}")


def load_setup(setup_id: str) -> Setup:
    _validate_setup_id(setup_id)
    path = CATALOG_ROOT / setup_id / "setup.json"
    if not path.is_file():
        fail(f"unknown setup: {setup_id}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid setup manifest {path}: {exc}")
    if data.get("schema_version") != 1 or data.get("id") != setup_id:
        fail(f"setup {setup_id}: manifest identity or schema is invalid")
    market = data.get("marketplace")
    if not isinstance(market, dict):
        fail(f"setup {setup_id}: missing marketplace object")
    name = market.get("name")
    source = market.get("source")
    plugins = market.get("plugins")
    if not isinstance(name, str) or not name:
        fail(f"setup {setup_id}: marketplace.name must be a non-empty string")
    if not isinstance(source, dict):
        fail(f"setup {setup_id}: marketplace.source must be an object")
    if not isinstance(plugins, list) or not all(isinstance(p, str) and p for p in plugins):
        fail(f"setup {setup_id}: marketplace.plugins must be a list of plugin names")
    return Setup(
        setup_id=setup_id,
        description=str(data.get("description", "")),
        marketplace_name=name,
        marketplace_source=source,
        auto_update=bool(market.get("auto_update", False)),
        plugins=tuple(plugins),
    )


def list_setups() -> list[Setup]:
    if not CATALOG_ROOT.is_dir():
        return []
    setups = []
    for child in sorted(CATALOG_ROOT.iterdir()):
        if child.is_dir() and (child / "setup.json").is_file():
            setups.append(load_setup(child.name))
    return setups


def render_managed(setup: Setup) -> dict[str, Any]:
    """The exact managed settings fragments this setup owns."""
    entry: dict[str, Any] = {"source": setup.marketplace_source}
    if setup.auto_update:
        entry["autoUpdate"] = True
    return {
        "marketplace_name": setup.marketplace_name,
        "marketplace_entry": entry,
        "enable_keys": list(setup.enable_keys),
    }


# --- target + filesystem safety --------------------------------------------


def resolve_target(raw: str) -> Path:
    if os.path.isabs(raw) is False:
        fail("--target must be an absolute path to a Claude Code home")
    path = Path(raw)
    if any(part in {".", ".."} for part in path.parts):
        fail("--target must not contain dot traversal")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        fail(f"--target parent must be an existing real directory: {parent}")
    if path.is_symlink():
        fail(f"refusing symlinked target: {path}")
    return path


def _read_json_file(path: Path, *, max_bytes: int) -> Any:
    if path.is_symlink():
        fail(f"refusing symlinked managed file: {path}")
    if path.stat().st_size > max_bytes:
        fail(f"managed file exceeds {max_bytes} bytes: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid JSON at {path}: {exc}")


def read_settings(target: Path) -> dict[str, Any]:
    path = target / SETTINGS_NAME
    if not path.exists():
        return {}
    value = _read_json_file(path, max_bytes=MANAGED_PAYLOAD_MAX_BYTES)
    if not isinstance(value, dict):
        fail(f"{path} must contain a JSON object")
    return value


def read_stamp(target: Path) -> dict[str, Any] | None:
    path = target / STAMP_NAME
    if not path.exists():
        return None
    value = _read_json_file(path, max_bytes=MANAGED_PAYLOAD_MAX_BYTES)
    if not isinstance(value, dict):
        return None
    if value.get("schema_version") != STAMP_SCHEMA or value.get("product_name") != PRODUCT_NAME:
        return None
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically (temp in the same dir + rename), owner-only mode."""
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directory, OWNER_DIR_MODE)
    except OSError:
        pass
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(directory))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, OWNER_FILE_MODE)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _remove_file(path: Path) -> None:
    if path.is_symlink():
        fail(f"refusing to remove symlink: {path}")
    path.unlink(missing_ok=True)


# --- managed-state model (overlay preservation) ----------------------------


def compose_settings(current: dict[str, Any], setup: Setup) -> dict[str, Any]:
    """Return current settings with only the managed keys added/updated. Every
    sibling key -- and every foreign entry inside the two managed maps -- is
    preserved verbatim."""
    managed = render_managed(setup)
    result = dict(current)
    marketplaces = dict(result.get(MARKETPLACES_KEY, {}) or {})
    marketplaces[managed["marketplace_name"]] = managed["marketplace_entry"]
    result[MARKETPLACES_KEY] = marketplaces
    enabled = dict(result.get(ENABLED_PLUGINS_KEY, {}) or {})
    for key in managed["enable_keys"]:
        enabled[key] = True
    result[ENABLED_PLUGINS_KEY] = enabled
    return result


def strip_managed(current: dict[str, Any], marketplace_name: str, enable_keys: list[str]) -> dict[str, Any]:
    """Return current settings with the given managed marketplace + enable keys
    removed, preserving all siblings. Empty managed maps are dropped."""
    result = dict(current)
    marketplaces = dict(result.get(MARKETPLACES_KEY, {}) or {})
    marketplaces.pop(marketplace_name, None)
    if marketplaces:
        result[MARKETPLACES_KEY] = marketplaces
    else:
        result.pop(MARKETPLACES_KEY, None)
    enabled = dict(result.get(ENABLED_PLUGINS_KEY, {}) or {})
    for key in enable_keys:
        enabled.pop(key, None)
    if enabled:
        result[ENABLED_PLUGINS_KEY] = enabled
    else:
        result.pop(ENABLED_PLUGINS_KEY, None)
    return result


def managed_state_present(settings: dict[str, Any], setup: Setup) -> bool:
    managed = render_managed(setup)
    marketplaces = settings.get(MARKETPLACES_KEY, {}) or {}
    if marketplaces.get(managed["marketplace_name"]) != managed["marketplace_entry"]:
        return False
    enabled = settings.get(ENABLED_PLUGINS_KEY, {}) or {}
    return all(enabled.get(key) is True for key in managed["enable_keys"])


def stamp_payload(setup: Setup) -> dict[str, Any]:
    return {
        "schema_version": STAMP_SCHEMA,
        "product_name": PRODUCT_NAME,
        "setup_id": setup.setup_id,
        "marketplace_name": setup.marketplace_name,
        "enabled_plugins": list(setup.enable_keys),
    }


# --- backups ---------------------------------------------------------------


def backups_dir(target: Path) -> Path:
    return target.parent / f".{target.name}.nddev-claude-backups"


def create_backup(target: Path) -> int | None:
    """Snapshot the two managed files into the next backup slot. Returns the slot
    index, or None when there is nothing managed to back up."""
    settings = target / SETTINGS_NAME
    stamp = target / STAMP_NAME
    if not settings.exists() and not stamp.exists():
        return None
    root = backups_dir(target)
    root.mkdir(mode=OWNER_DIR_MODE, parents=True, exist_ok=True)
    used = sorted(int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit())
    slot = (used[-1] + 1) if used else 0
    slot_dir = root / str(slot)
    slot_dir.mkdir(mode=OWNER_DIR_MODE)
    for source in (settings, stamp):
        if source.exists() and not source.is_symlink():
            shutil.copy2(source, slot_dir / source.name)
    # Rotate: keep only the most recent MAX_BACKUPS slots.
    for old in used[: max(0, len(used) + 1 - MAX_BACKUPS)]:
        shutil.rmtree(root / str(old), ignore_errors=True)
    return slot


def restore_backup(target: Path, slot: int) -> None:
    slot_dir = backups_dir(target) / str(slot)
    if not slot_dir.is_dir():
        fail(f"backup slot not found: {slot}")
    for name in (SETTINGS_NAME, STAMP_NAME):
        source = slot_dir / name
        dest = target / name
        if source.exists():
            _atomic_write_json(dest, _read_json_file(source, max_bytes=MANAGED_PAYLOAD_MAX_BYTES))
        else:
            _remove_file(dest)


# --- inspection ------------------------------------------------------------


def inspect_target(target: Path) -> dict[str, Any]:
    if not target.exists():
        return {"state": "missing", "setup_id": None, "drift": []}
    stamp = read_stamp(target)
    if stamp is None:
        return {"state": "unmanaged", "setup_id": None, "drift": []}
    setup_id = stamp.get("setup_id")
    drift: list[str] = []
    try:
        setup = load_setup(str(setup_id))
    except ManagerError:
        return {"state": "managed", "setup_id": setup_id, "drift": ["setup"]}
    settings = read_settings(target)
    if not managed_state_present(settings, setup):
        drift.append(SETTINGS_NAME)
    return {"state": "managed", "setup_id": setup_id, "drift": drift}


# --- transactional operations ----------------------------------------------


def _commit(target: Path, new_settings: dict[str, Any], setup: Setup | None) -> int | None:
    """Atomically write settings + stamp with a fresh backup and rollback."""
    slot = create_backup(target)
    settings_path = target / SETTINGS_NAME
    stamp_path = target / STAMP_NAME
    before_settings = settings_path.read_bytes() if settings_path.exists() else None
    before_stamp = stamp_path.read_bytes() if stamp_path.exists() else None
    try:
        _atomic_write_json(settings_path, new_settings)
        if setup is None:
            _remove_file(stamp_path)
        else:
            _atomic_write_json(stamp_path, stamp_payload(setup))
    except BaseException:
        # Roll back to exact prior bytes.
        if before_settings is None:
            _remove_file(settings_path)
        else:
            settings_path.write_bytes(before_settings)
        if before_stamp is None:
            _remove_file(stamp_path)
        else:
            stamp_path.write_bytes(before_stamp)
        raise
    return slot


def plan(target: Path, setup: Setup) -> dict[str, Any]:
    status = inspect_target(target)
    if status["state"] == "managed" and status["setup_id"] == setup.setup_id and not status["drift"]:
        operation = "noop"
    elif status["state"] in {"missing", "unmanaged"}:
        operation = "install"
    elif status["setup_id"] == setup.setup_id:
        operation = "update"
    else:
        operation = "switch"
    return {
        "command": "plan",
        "target": str(target),
        "setup_id": setup.setup_id,
        "operation": operation,
        "marketplace": setup.marketplace_name,
        "enables": list(setup.enable_keys),
        "mutates": False,
    }


def apply_setup(target: Path, setup: Setup, *, command: str) -> dict[str, Any]:
    prior = inspect_target(target)
    if command == "switch" and prior["state"] != "managed":
        fail("switch requires a target already managed by nddev-claude-app")
    if command == "switch" and prior["setup_id"] == setup.setup_id:
        fail("switch requires a different setup; use apply to update in place")
    settings = read_settings(target)
    # If switching from a prior managed setup, strip its keys first so a renamed
    # marketplace/plugin does not leave an orphaned enable flag.
    if prior["state"] == "managed" and prior["setup_id"] not in (None, setup.setup_id):
        try:
            old = load_setup(str(prior["setup_id"]))
            settings = strip_managed(settings, old.marketplace_name, list(old.enable_keys))
        except ManagerError:
            pass
    composed = compose_settings(settings, setup)
    slot = _commit(target, composed, setup)
    return {
        "command": command,
        "target": str(target),
        "setup_id": setup.setup_id,
        "backup_slot": slot,
        "changed": True,
    }


def remove_setup(target: Path) -> dict[str, Any]:
    status = inspect_target(target)
    if status["state"] != "managed":
        fail("target is not managed by nddev-claude-app")
    settings = read_settings(target)
    try:
        setup = load_setup(str(status["setup_id"]))
        settings = strip_managed(settings, setup.marketplace_name, list(setup.enable_keys))
    except ManagerError:
        stamp = read_stamp(target) or {}
        settings = strip_managed(
            settings,
            str(stamp.get("marketplace_name", "")),
            list(stamp.get("enabled_plugins", []) or []),
        )
    slot = _commit(target, settings, None)
    return {
        "command": "remove",
        "target": str(target),
        "removed_setup_id": status["setup_id"],
        "backup_slot": slot,
    }


# --- CLI -------------------------------------------------------------------


def _emit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nddev_claude.py", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List source setups.")

    def target_command(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--target", required=True, help="Absolute Claude Code home.")
        sub.add_argument("--json", action="store_true", help="Emit JSON.")
        return sub

    target_command("status", "Inspect an explicit target.")
    for command in ("plan", "apply", "switch"):
        sub = target_command(command, f"{command.title()} a setup.")
        sub.add_argument("--setup", required=True, help="Setup id from the catalog.")
    restore = target_command("restore", "Restore a target-bound backup.")
    restore.add_argument("--backup", type=int, required=True, help="Backup slot 0..9.")
    target_command("remove", "Remove only managed setup state.")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the CLI without side effects, so documented commands are provable."""
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "list":
            setups = [
                {"id": s.setup_id, "marketplace": s.marketplace_name, "description": s.description}
                for s in list_setups()
            ]
            print(json.dumps({"setups": setups}, indent=2))
            return 0

        target = resolve_target(args.target)
        as_json = getattr(args, "json", False)

        if args.command == "status":
            _emit(inspect_target(target), as_json)
        elif args.command == "plan":
            _emit(plan(target, load_setup(args.setup)), as_json)
        elif args.command == "apply":
            _emit(apply_setup(target, load_setup(args.setup), command="apply"), as_json)
        elif args.command == "switch":
            _emit(apply_setup(target, load_setup(args.setup), command="switch"), as_json)
        elif args.command == "remove":
            _emit(remove_setup(target), as_json)
        elif args.command == "restore":
            restore_backup(target, args.backup)
            _emit(inspect_target(target), as_json)
        else:  # pragma: no cover - argparse enforces the choice set
            fail(f"unknown command: {args.command}")
        return 0
    except ManagerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
