#!/usr/bin/env python3
"""NDDev Claude Code setup manager.

Registers, updates, switches, and removes a selected NDDev marketplace of
Claude Code plugins in a caller-selected Claude Code config directory (an
explicit ``--target`` directory, never an inferred ``~/.claude``). The manager
owns *only* two keys in the target's ``settings.json`` -- its marketplace entry
under ``extraKnownMarketplaces`` and its plugin-enable flags under
``enabledPlugins`` -- plus its own stamp file. Every other settings key,
``.credentials.json``, ``projects/``, and the Claude-CLI-owned ``plugins/``
registry are preserved verbatim. Mutations are locked, staged in a unique
transaction directory, backed up to a target-bound slot, and rolled back on
failure.

Dependency-free; standard library only; Python >= 3.10.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import stat
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
BACKUP_POOL_MARKER_NAME = "NDDEV-CLAUDE-BACKUPS.json"
BACKUP_SLOT_MARKER_NAME = "NDDEV-CLAUDE-BACKUP.json"
BACKUP_SCHEMA = 1
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
    parent_st = _lstat_optional(parent)
    if parent_st is None:
        fail(f"--target parent must be an existing real directory: {parent}")
    _require_directory(parent, parent_st, label="--target parent", private=True)
    target_st = _lstat_optional(path)
    if target_st is not None:
        _require_directory(path, target_st, label="--target", private=True)
    return path


def _lstat_optional(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        fail(f"cannot inspect {path}: {exc}")


def _current_uid() -> int:
    return os.getuid()


def _mode(st: os.stat_result) -> int:
    return stat.S_IMODE(st.st_mode)


def _target_key(target: Path) -> str:
    return str(target.resolve(strict=False))


def _require_current_owner(path: Path, st: os.stat_result) -> None:
    if st.st_uid != _current_uid():
        fail(f"refusing path not owned by current user: {path}")


def _reject_symlink(path: Path, st: os.stat_result) -> None:
    if stat.S_ISLNK(st.st_mode):
        fail(f"refusing symlinked path: {path}")


def _require_directory(
    path: Path,
    st: os.stat_result,
    *,
    label: str = "directory",
    private: bool,
) -> None:
    _reject_symlink(path, st)
    if not stat.S_ISDIR(st.st_mode):
        fail(f"{label} must be a real directory: {path}")
    _require_current_owner(path, st)
    mode = _mode(st)
    if private and (mode & 0o077 or (mode & 0o700) != 0o700):
        fail(f"{label} must be private (0700-compatible): {path}")
    if not private and mode & 0o022:
        fail(f"{label} must not be group/world writable: {path}")


def _require_regular_managed_file(path: Path, st: os.stat_result) -> None:
    _reject_symlink(path, st)
    if not stat.S_ISREG(st.st_mode):
        fail(f"managed file must be a regular file: {path}")
    _require_current_owner(path, st)
    if st.st_nlink != 1:
        fail(f"refusing hardlinked managed file: {path}")
    mode = _mode(st)
    if mode & 0o077 or (mode & 0o600) != 0o600:
        fail(f"managed file must be private (0600-compatible): {path}")


def _read_managed_bytes(path: Path, *, max_bytes: int) -> bytes:
    st_before = _lstat_optional(path)
    if st_before is None:
        fail(f"managed file is missing: {path}")
    _require_regular_managed_file(path, st_before)
    if st_before.st_size > max_bytes:
        fail(f"managed file exceeds {max_bytes} bytes: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        fail(f"cannot open managed file without following links {path}: {exc}")
    try:
        st_fd = os.fstat(fd)
        if st_fd.st_dev != st_before.st_dev or st_fd.st_ino != st_before.st_ino:
            fail(f"managed file changed during read: {path}")
        _require_regular_managed_file(path, st_fd)
        with os.fdopen(fd, "rb") as handle:
            data = handle.read(max_bytes + 1)
            fd = -1
    finally:
        if fd >= 0:
            os.close(fd)
    if len(data) > max_bytes:
        fail(f"managed file exceeds {max_bytes} bytes: {path}")
    st_after = _lstat_optional(path)
    if st_after is None or st_after.st_dev != st_before.st_dev or st_after.st_ino != st_before.st_ino:
        fail(f"managed file changed during read: {path}")
    return data


def _read_json_file(path: Path, *, max_bytes: int) -> Any:
    data = _read_managed_bytes(path, max_bytes=max_bytes)
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid JSON at {path}: {exc}")


def read_settings(target: Path) -> dict[str, Any]:
    path = target / SETTINGS_NAME
    if _lstat_optional(path) is None:
        return {}
    value = _read_json_file(path, max_bytes=MANAGED_PAYLOAD_MAX_BYTES)
    if not isinstance(value, dict):
        fail(f"{path} must contain a JSON object")
    return value


def read_stamp(target: Path) -> dict[str, Any] | None:
    path = target / STAMP_NAME
    if _lstat_optional(path) is None:
        return None
    value = _read_json_file(path, max_bytes=MANAGED_PAYLOAD_MAX_BYTES)
    if not isinstance(value, dict):
        return None
    if value.get("schema_version") != STAMP_SCHEMA or value.get("product_name") != PRODUCT_NAME:
        return None
    return value


def _write_bytes_atomic(path: Path, data: bytes, *, mode: int, transaction_dir: Path) -> None:
    """Write bytes atomically from a caller-owned transaction directory."""
    target_dir_st = _lstat_optional(path.parent)
    if target_dir_st is None:
        fail(f"managed directory is missing: {path.parent}")
    _require_directory(path.parent, target_dir_st, label="managed directory", private=True)
    transaction_st = _lstat_optional(transaction_dir)
    if transaction_st is None:
        fail(f"transaction directory is missing: {transaction_dir}")
    _require_directory(transaction_dir, transaction_st, label="transaction directory", private=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(transaction_dir))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp_st = tmp.lstat()
            _reject_symlink(tmp, tmp_st)
            tmp.unlink()


def _atomic_write_json(path: Path, payload: dict[str, Any], *, transaction_dir: Path) -> None:
    """Write JSON atomically (temp in the same dir + rename), owner-only mode."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    _write_bytes_atomic(
        path,
        text.encode("utf-8"),
        mode=OWNER_FILE_MODE,
        transaction_dir=transaction_dir,
    )


def _remove_file(path: Path) -> None:
    st = _lstat_optional(path)
    if st is None:
        return
    _require_regular_managed_file(path, st)
    path.unlink()


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


def strip_managed(
    current: dict[str, Any], marketplace_name: str, enable_keys: list[str]
) -> dict[str, Any]:
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


@dataclass(frozen=True)
class ManagedFileSnapshot:
    exists: bool
    content: bytes = b""
    mode: int = OWNER_FILE_MODE


@dataclass(frozen=True)
class TargetSnapshot:
    exists: bool
    mode: int = OWNER_DIR_MODE


@dataclass(frozen=True)
class BackupSlot:
    slot: int
    marker: dict[str, Any]


def backups_dir(target: Path) -> Path:
    return target.parent / f".{target.name}.nddev-claude-backups"


def _backup_pool_payload(target: Path) -> dict[str, Any]:
    return {
        "schema_version": BACKUP_SCHEMA,
        "product_name": PRODUCT_NAME,
        "canonical_target": _target_key(target),
    }


def _validate_backup_pool(target: Path, root: Path) -> bool:
    st = _lstat_optional(root)
    if st is None:
        return False
    _require_directory(root, st, label="backup directory", private=True)
    marker_path = root / BACKUP_POOL_MARKER_NAME
    marker = _read_json_file(marker_path, max_bytes=MANAGED_PAYLOAD_MAX_BYTES)
    if marker != _backup_pool_payload(target):
        fail(f"backup directory is not bound to target: {root}")
    return True


def _ensure_backup_pool(
    target: Path,
    *,
    transaction_dir: Path,
    created_dirs: list[Path],
) -> Path:
    root = backups_dir(target)
    if _validate_backup_pool(target, root):
        return root
    try:
        os.mkdir(root, OWNER_DIR_MODE)
    except FileExistsError:
        fail(f"backup directory exists without nddev ownership marker: {root}")
    except OSError as exc:
        fail(f"cannot create backup directory {root}: {exc}")
    os.chmod(root, OWNER_DIR_MODE)
    created_dirs.append(root)
    _atomic_write_json(
        root / BACKUP_POOL_MARKER_NAME,
        _backup_pool_payload(target),
        transaction_dir=transaction_dir,
    )
    return root


def _file_snapshot(path: Path) -> ManagedFileSnapshot:
    st = _lstat_optional(path)
    if st is None:
        return ManagedFileSnapshot(exists=False)
    content = _read_managed_bytes(path, max_bytes=MANAGED_PAYLOAD_MAX_BYTES)
    return ManagedFileSnapshot(exists=True, content=content, mode=_mode(st))


def _target_snapshot(target: Path) -> TargetSnapshot:
    st = _lstat_optional(target)
    if st is None:
        return TargetSnapshot(exists=False)
    _require_directory(target, st, label="--target", private=True)
    return TargetSnapshot(exists=True, mode=_mode(st))


def _snapshot_metadata(snapshot: ManagedFileSnapshot) -> dict[str, Any]:
    if not snapshot.exists:
        return {"present": False}
    return {
        "present": True,
        "mode": f"{snapshot.mode:04o}",
        "sha256": hashlib.sha256(snapshot.content).hexdigest(),
        "size": len(snapshot.content),
    }


def _write_snapshot(
    path: Path,
    snapshot: ManagedFileSnapshot,
    *,
    transaction_dir: Path,
) -> None:
    if not snapshot.exists:
        _remove_file(path)
        return
    _write_bytes_atomic(
        path,
        snapshot.content,
        mode=snapshot.mode,
        transaction_dir=transaction_dir,
    )


def _backup_slot_marker(target: Path, snapshots: dict[str, ManagedFileSnapshot]) -> dict[str, Any]:
    return {
        "schema_version": BACKUP_SCHEMA,
        "product_name": PRODUCT_NAME,
        "canonical_target": _target_key(target),
        "files": {name: _snapshot_metadata(snapshot) for name, snapshot in snapshots.items()},
    }


def _validate_backup_slot(target: Path, slot_dir: Path) -> BackupSlot | None:
    st = _lstat_optional(slot_dir)
    if st is None:
        return None
    _require_directory(slot_dir, st, label="backup slot", private=True)
    marker_path = slot_dir / BACKUP_SLOT_MARKER_NAME
    if _lstat_optional(marker_path) is None:
        return None
    marker = _read_json_file(marker_path, max_bytes=MANAGED_PAYLOAD_MAX_BYTES)
    if not isinstance(marker, dict):
        fail(f"backup slot marker must be a JSON object: {marker_path}")
    if (
        marker.get("schema_version") != BACKUP_SCHEMA
        or marker.get("product_name") != PRODUCT_NAME
        or marker.get("canonical_target") != _target_key(target)
    ):
        fail(f"backup slot is not bound to target: {slot_dir}")
    try:
        slot = int(slot_dir.name)
    except ValueError:
        return None
    return BackupSlot(slot=slot, marker=marker)


def _existing_backup_slots(target: Path, root: Path) -> list[BackupSlot]:
    slots: list[BackupSlot] = []
    for child in root.iterdir():
        if not child.name.isdigit():
            continue
        slot = _validate_backup_slot(target, child)
        if slot is not None:
            slots.append(slot)
    return sorted(slots, key=lambda item: item.slot)


def _remove_created_dir(path: Path) -> None:
    st = _lstat_optional(path)
    if st is None:
        return
    _require_directory(path, st, label="created directory", private=True)
    shutil.rmtree(path)


def _remove_backup_slot(target: Path, root: Path, slot: int) -> None:
    slot_dir = root / str(slot)
    slot_info = _validate_backup_slot(target, slot_dir)
    if slot_info is None:
        fail(f"refusing to remove unmarked backup slot: {slot_dir}")
    _remove_created_dir(slot_dir)


def create_backup(
    target: Path,
    *,
    transaction_dir: Path,
    created_dirs: list[Path],
) -> int | None:
    """Snapshot the two managed files into the next backup slot. Returns the slot
    index, or None when there is nothing managed to back up."""
    settings = target / SETTINGS_NAME
    stamp = target / STAMP_NAME
    snapshots = {
        SETTINGS_NAME: _file_snapshot(settings),
        STAMP_NAME: _file_snapshot(stamp),
    }
    if not any(snapshot.exists for snapshot in snapshots.values()):
        return None
    root = _ensure_backup_pool(target, transaction_dir=transaction_dir, created_dirs=created_dirs)
    numeric_children = sorted(int(p.name) for p in root.iterdir() if p.name.isdigit())
    used_slots = _existing_backup_slots(target, root)
    slot = (numeric_children[-1] + 1) if numeric_children else 0
    slot_dir = root / str(slot)
    try:
        os.mkdir(slot_dir, OWNER_DIR_MODE)
    except FileExistsError:
        fail(f"backup slot collision: {slot_dir}")
    except OSError as exc:
        fail(f"cannot create backup slot {slot_dir}: {exc}")
    os.chmod(slot_dir, OWNER_DIR_MODE)
    created_dirs.append(slot_dir)
    for name, snapshot in snapshots.items():
        if snapshot.exists:
            _write_bytes_atomic(
                slot_dir / name,
                snapshot.content,
                mode=snapshot.mode,
                transaction_dir=transaction_dir,
            )
    _atomic_write_json(
        slot_dir / BACKUP_SLOT_MARKER_NAME,
        _backup_slot_marker(target, snapshots),
        transaction_dir=transaction_dir,
    )
    keep = {item.slot for item in used_slots[-(MAX_BACKUPS - 1) :]} if MAX_BACKUPS > 1 else set()
    for old in used_slots:
        if old.slot not in keep:
            _remove_backup_slot(target, root, old.slot)
    return slot


def restore_backup(target: Path, slot: int) -> None:
    with _target_lock(target):
        transaction_dir = _create_transaction_dir(target)
        created_dirs = [transaction_dir]
        target_snapshot = _target_snapshot(target)
        settings_snapshot = _file_snapshot(target / SETTINGS_NAME)
        stamp_snapshot = _file_snapshot(target / STAMP_NAME)
        try:
            _ensure_target_for_write(target)
            root = backups_dir(target)
            if not _validate_backup_pool(target, root):
                fail(f"backup slot not found: {slot}")
            slot_dir = root / str(slot)
            slot_info = _validate_backup_slot(target, slot_dir)
            if slot_info is None:
                fail(f"backup slot not found: {slot}")
            _restore_backup_slot(target, slot_dir, slot_info.marker, transaction_dir=transaction_dir)
        except BaseException:
            _restore_transaction(
                target,
                target_snapshot,
                {
                    SETTINGS_NAME: settings_snapshot,
                    STAMP_NAME: stamp_snapshot,
                },
                transaction_dir=transaction_dir,
            )
            raise
        finally:
            for created in sorted(created_dirs, key=lambda p: len(p.parts), reverse=True):
                _remove_created_dir(created)


def _verify_backup_file(
    slot_dir: Path,
    name: str,
    expected: dict[str, Any],
) -> ManagedFileSnapshot:
    if expected.get("present") is False:
        if _lstat_optional(slot_dir / name) is not None:
            fail(f"backup marker says {name} is absent but file exists")
        return ManagedFileSnapshot(exists=False)
    if expected.get("present") is not True:
        fail(f"backup marker has invalid presence for {name}")
    mode_text = expected.get("mode")
    if not isinstance(mode_text, str):
        fail(f"backup marker missing mode for {name}")
    try:
        mode = int(mode_text, 8)
    except ValueError:
        fail(f"backup marker has invalid mode for {name}")
    content = _read_managed_bytes(slot_dir / name, max_bytes=MANAGED_PAYLOAD_MAX_BYTES)
    digest = hashlib.sha256(content).hexdigest()
    if digest != expected.get("sha256"):
        fail(f"backup file digest mismatch for {name}")
    if len(content) != expected.get("size"):
        fail(f"backup file size mismatch for {name}")
    return ManagedFileSnapshot(exists=True, content=content, mode=mode)


def _restore_backup_slot(
    target: Path,
    slot_dir: Path,
    marker: dict[str, Any],
    *,
    transaction_dir: Path,
) -> None:
    files = marker.get("files")
    if not isinstance(files, dict):
        fail(f"backup slot marker missing files: {slot_dir}")
    for name in (SETTINGS_NAME, STAMP_NAME):
        expected = files.get(name)
        if not isinstance(expected, dict):
            fail(f"backup slot marker missing {name}: {slot_dir}")
        snapshot = _verify_backup_file(slot_dir, name, expected)
        _write_snapshot(target / name, snapshot, transaction_dir=transaction_dir)


def _ensure_target_for_write(target: Path) -> bool:
    st = _lstat_optional(target)
    if st is None:
        try:
            os.mkdir(target, OWNER_DIR_MODE)
        except FileExistsError:
            st = _lstat_optional(target)
            if st is None:
                fail(f"target appeared but cannot be inspected: {target}")
            _require_directory(target, st, label="--target", private=True)
            return False
        except OSError as exc:
            fail(f"cannot create target {target}: {exc}")
        os.chmod(target, OWNER_DIR_MODE)
        st = _lstat_optional(target)
        if st is None:
            fail(f"created target disappeared: {target}")
        _require_directory(target, st, label="--target", private=True)
        return True
    _require_directory(target, st, label="--target", private=True)
    return False


def _create_transaction_dir(target: Path) -> Path:
    parent_st = _lstat_optional(target.parent)
    if parent_st is None:
        fail(f"--target parent must be an existing real directory: {target.parent}")
    _require_directory(target.parent, parent_st, label="--target parent", private=True)
    try:
        name = tempfile.mkdtemp(prefix=f".{target.name}.nddev-claude-txn-", dir=str(target.parent))
    except OSError as exc:
        fail(f"cannot create transaction directory in {target.parent}: {exc}")
    path = Path(name)
    os.chmod(path, OWNER_DIR_MODE)
    st = _lstat_optional(path)
    if st is None:
        fail(f"transaction directory disappeared: {path}")
    _require_directory(path, st, label="transaction directory", private=True)
    return path


@contextlib.contextmanager
def _target_lock(target: Path):
    parent_st = _lstat_optional(target.parent)
    if parent_st is None:
        fail(f"--target parent must be an existing real directory: {target.parent}")
    _require_directory(target.parent, parent_st, label="--target parent", private=True)
    lock_dir = target.parent / f".{target.name}.nddev-claude-lock"
    created = False
    try:
        try:
            os.mkdir(lock_dir, OWNER_DIR_MODE)
        except FileExistsError:
            fail(f"target is locked by another nddev-claude-app transaction: {lock_dir}")
        except OSError as exc:
            fail(f"cannot create target lock {lock_dir}: {exc}")
        created = True
        os.chmod(lock_dir, OWNER_DIR_MODE)
        marker = lock_dir / "owner.json"
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, OWNER_FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"product_name": PRODUCT_NAME, "pid": os.getpid()}, handle, sort_keys=True)
            handle.write("\n")
        yield
    finally:
        if created:
            _remove_created_dir(lock_dir)


def _restore_transaction(
    target: Path,
    target_snapshot: TargetSnapshot,
    file_snapshots: dict[str, ManagedFileSnapshot],
    *,
    transaction_dir: Path,
) -> None:
    if target_snapshot.exists:
        _ensure_target_for_write(target)
        for name, snapshot in file_snapshots.items():
            _write_snapshot(target / name, snapshot, transaction_dir=transaction_dir)
        with contextlib.suppress(OSError):
            os.chmod(target, target_snapshot.mode)
    else:
        for name in (SETTINGS_NAME, STAMP_NAME):
            _remove_file(target / name)
        with contextlib.suppress(OSError):
            target.rmdir()


# --- inspection ------------------------------------------------------------


def inspect_target(target: Path) -> dict[str, Any]:
    target_st = _lstat_optional(target)
    if target_st is None:
        return {"state": "missing", "setup_id": None, "drift": []}
    _require_directory(target, target_st, label="--target", private=True)
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


def _commit_locked(target: Path, new_settings: dict[str, Any], setup: Setup | None) -> int | None:
    """Atomically write settings + stamp with a fresh backup and rollback."""
    transaction_dir = _create_transaction_dir(target)
    transaction_dirs = [transaction_dir]
    backup_created_dirs: list[Path] = []
    settings_path = target / SETTINGS_NAME
    stamp_path = target / STAMP_NAME
    target_snapshot = _target_snapshot(target)
    before_settings = _file_snapshot(settings_path)
    before_stamp = _file_snapshot(stamp_path)
    created_target = False
    try:
        created_target = _ensure_target_for_write(target)
        slot = create_backup(
            target,
            transaction_dir=transaction_dir,
            created_dirs=backup_created_dirs,
        )
        _atomic_write_json(settings_path, new_settings, transaction_dir=transaction_dir)
        if setup is None:
            _remove_file(stamp_path)
        else:
            _atomic_write_json(
                stamp_path,
                stamp_payload(setup),
                transaction_dir=transaction_dir,
            )
    except BaseException:
        _restore_transaction(
            target,
            target_snapshot,
            {
                SETTINGS_NAME: before_settings,
                STAMP_NAME: before_stamp,
            },
            transaction_dir=transaction_dir,
        )
        for created in sorted(backup_created_dirs, key=lambda p: len(p.parts), reverse=True):
            _remove_created_dir(created)
        if created_target and not target_snapshot.exists:
            with contextlib.suppress(OSError):
                target.rmdir()
        raise
    finally:
        for created in sorted(transaction_dirs, key=lambda p: len(p.parts), reverse=True):
            _remove_created_dir(created)
    return slot


def plan(target: Path, setup: Setup) -> dict[str, Any]:
    status = inspect_target(target)
    if (
        status["state"] == "managed"
        and status["setup_id"] == setup.setup_id
        and not status["drift"]
    ):
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
    with _target_lock(target):
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
        slot = _commit_locked(target, composed, setup)
    return {
        "command": command,
        "target": str(target),
        "setup_id": setup.setup_id,
        "backup_slot": slot,
        "changed": True,
    }


def remove_setup(target: Path) -> dict[str, Any]:
    with _target_lock(target):
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
        slot = _commit_locked(target, settings, None)
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
