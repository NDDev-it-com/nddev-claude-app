#!/usr/bin/env python3
"""Validate the public NDDev Claude Code module contracts without private inputs.

Checks only tracked public contract files: the public contract, the build
manifest and version, the plugin marketplace + plugin manifests, and their
version parity. Fails closed with a non-zero exit and one error per problem.
Dependency-free; standard library only.
"""

from __future__ import annotations

import json
import re
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = (
    "VERSION",
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CHANGELOG.md",
    "config/nddev-contract.json",
    "build/manifest.json",
    "build/version.json",
    "cli-tools/nddev_claude.py",
    ".claude-plugin/marketplace.json",
    "plugins/nddev-builder/.claude-plugin/plugin.json",
    "setups/stable/setup.json",
    "setups/edge/setup.json",
)

PUBLIC_BASELINE_KEYS = {
    "schema_version",
    "product",
    "verified_against",
    "official_sources",
    "config_dir",
    "config_dir_env",
    "settings_file",
    "managed_settings_keys",
    "cli_owned",
    "never_touch",
    "settings_surface",
    "native_plugin_surfaces",
    "plugin_manifest",
    "marketplace_manifest",
    "plugin_manifest_required",
    "marketplace_manifest_required",
}
PRIVATE_OBSERVATION_KEYS = {
    "verified_at",
    "distribution",
    "native_release_manifest",
    "npm_packument",
    "dist_tags",
    "latest_tarball",
    "installer_audit",
    "install_sh_sha256",
    "install_ps1_sha256",
    "buildDate",
    "commit",
    "platforms",
    "binary",
    "checksum",
    "size",
}


def is_real_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def is_real_directory(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def load_json(relative: str, errors: list[str]) -> dict | None:
    path = ROOT / relative
    if not is_real_file(path):
        errors.append(f"missing required contract file: {relative}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{relative}: invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{relative}: expected a JSON object")
        return None
    return value


def resolve_version_ref(ref: str, version: dict, errors: list[str]) -> str | None:
    file_ref, _, selector = ref.partition(":")
    if file_ref != "build/version.json" or not selector:
        errors.append(f"unexpected version ref: {ref}")
        return None
    value = version.get(selector)
    if not isinstance(value, str):
        errors.append(f"build/version.json missing string key: {selector}")
        return None
    return value


def require_bool(
    container: dict, key: str, expected: bool, context: str, errors: list[str]
) -> None:
    if container.get(key) is not expected:
        errors.append(f"{context}: {key} must be {expected}")


def require_string(
    container: dict, key: str, expected: str, context: str, errors: list[str]
) -> None:
    if container.get(key) != expected:
        errors.append(f"{context}: {key} must be {expected!r}")


def find_keys(value: object, forbidden: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(set(value) & forbidden)
        for child in value.values():
            found.update(find_keys(child, forbidden))
    elif isinstance(value, list):
        for child in value:
            found.update(find_keys(child, forbidden))
    return found


def validate_manager_source(errors: list[str]) -> None:
    source = (ROOT / "cli-tools/nddev_claude.py").read_text(encoding="utf-8")
    forbidden = (
        "subprocess",
        "os.system",
        "os.exec",
        "posix_spawn",
        "Popen",
        "claude --",
        " claude ",
    )
    for token in forbidden:
        if token in source:
            errors.append(f"cli-tools/nddev_claude.py must not execute Claude Code ({token})")
    required_patterns = (
        r"\.lstat\(",
        r"O_NOFOLLOW",
        r"st_nlink",
        r"nddev-claude-lock",
        r"nddev-claude-txn-",
        r"NDDEV-CLAUDE-BACKUP\.json",
        r"canonical_target",
    )
    for pattern in required_patterns:
        if not re.search(pattern, source):
            errors.append(f"cli-tools/nddev_claude.py missing safety primitive: {pattern}")


def main() -> int:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not is_real_file(ROOT / relative):
            errors.append(f"missing required public file: {relative}")

    for relative in ("AGENTS.md", ".claude/CLAUDE.md"):
        if not is_real_file(ROOT / relative):
            errors.append(f"required instruction path is not a regular file: {relative}")
    claude_dir = ROOT / ".claude"
    if not is_real_directory(claude_dir):
        errors.append("required instruction path is not a real directory: .claude")
    elif {path.name for path in claude_dir.iterdir()} != {"CLAUDE.md"}:
        errors.append(".claude contains unexpected entries")
    elif (claude_dir / "CLAUDE.md").read_bytes() != b"@../AGENTS.md\n":
        errors.append(".claude/CLAUDE.md must be the exact AGENTS.md bridge")

    contract = load_json("config/nddev-contract.json", errors)
    manifest = load_json("build/manifest.json", errors)
    version = load_json("build/version.json", errors)
    baseline = load_json("references/claude-baseline.json", errors)
    validate_manager_source(errors)

    if contract is not None:
        if contract.get("contract_version") != 1:
            errors.append("config/nddev-contract.json: contract_version must be 1")
        if contract.get("github_repository") != "NDDev-it-com/nddev-claude-app":
            errors.append("config/nddev-contract.json: unexpected github_repository")
        if contract.get("license") != "AGPL-3.0-or-later":
            errors.append("config/nddev-contract.json: license must be AGPL-3.0-or-later")
        if contract.get("product_name") != "nddev-claude-app":
            errors.append("config/nddev-contract.json: product_name mismatch")
        market = contract.get("plugin_marketplace", {})
        if not (ROOT / market.get("plugin_manifest", "")).is_file():
            errors.append("contract plugin_manifest does not resolve")
        if not (ROOT / market.get("marketplace_manifest", "")).is_file():
            errors.append("contract marketplace_manifest does not resolve")
        setup_system = contract.get("setup_system", {})
        require_bool(setup_system, "plan_mutates", False, "setup_system", errors)
        managed_state = contract.get("managed_state", {})
        require_string(managed_state, "target_env", "CLAUDE_CONFIG_DIR", "managed_state", errors)
        safety = contract.get("safety", {})
        for key in (
            "preserve_unmanaged_files",
            "reject_symlink_managed_files",
            "rollback_on_failure",
        ):
            require_bool(safety, key, True, "safety", errors)

    if manifest is not None and version is not None:
        if manifest.get("build_version") != version.get("build_version"):
            errors.append("build_version mismatch between manifest.json and version.json")
        if version.get("claude_code_tested") != "2.1.222":
            errors.append("build/version.json: claude_code_tested must be 2.1.222")
        if version.get("claude_code_min") != "2.1.154":
            errors.append("build/version.json: claude_code_min must be 2.1.154")
        command_policy = manifest.get("command_policy", {})
        require_bool(command_policy, "plan_mutates", False, "command_policy", errors)
        require_bool(command_policy, "status_mutates", False, "command_policy", errors)
        require_bool(command_policy, "executes_claude_binary", False, "command_policy", errors)
        require_bool(command_policy, "software_lifecycle_managed", False, "command_policy", errors)
        transaction_policy = manifest.get("transaction_policy", {})
        for key in (
            "target_parent_private_current_user",
            "target_private_current_user",
            "managed_files_no_follow",
            "managed_files_reject_hardlinks",
            "reject_dangling_symlinks",
            "reject_non_private_or_non_owned_paths",
            "exact_rollback_bytes_modes_target_existence",
            "fresh_failure_cleanup",
            "rollback_on_failure",
            "atomic_rename",
        ):
            require_bool(transaction_policy, key, True, "transaction_policy", errors)
        market = manifest.get("plugin_marketplace", {})
        ref = market.get("plugin_version_ref", "")
        plugin_version = resolve_version_ref(ref, version, errors)
        plugin_manifest = load_json(market.get("plugin_manifest", ""), errors)
        if plugin_manifest is not None and plugin_version is not None:
            if plugin_manifest.get("name") != "nddev-builder":
                errors.append("plugin.json name must be nddev-builder")
            if plugin_manifest.get("version") != plugin_version:
                errors.append(
                    "plugin.json version does not match build/version.json:"
                    "nddev_builder_plugin_version"
                )
        runtime = manifest.get("runtime_compatibility", {})
        if runtime.get("min_version_ref") != "build/version.json:claude_code_min":
            errors.append("manifest runtime_compatibility missing claude_code_min ref")

    marketplace = load_json(".claude-plugin/marketplace.json", errors)
    if marketplace is not None:
        if (
            marketplace.get("$schema")
            != "https://json.schemastore.org/claude-code-marketplace.json"
        ):
            errors.append(".claude-plugin/marketplace.json schema URL is required")
        if marketplace.get("name") != "nddev-builder":
            errors.append(".claude-plugin/marketplace.json name must be nddev-builder")
        if marketplace.get("version") != "0.1.0":
            errors.append(".claude-plugin/marketplace.json version must be 0.1.0")
        owner = marketplace.get("owner")
        if not isinstance(owner, dict) or not owner.get("name"):
            errors.append(".claude-plugin/marketplace.json owner.name is required")
        plugins = marketplace.get("plugins")
        if not isinstance(plugins, list) or not plugins:
            errors.append(".claude-plugin/marketplace.json plugins[] must be non-empty")
        else:
            for entry in plugins:
                if not isinstance(entry, dict) or not entry.get("name") or not entry.get("source"):
                    errors.append("marketplace plugin entry requires name and source")
                if isinstance(entry, dict) and entry.get("version") != "0.1.0":
                    errors.append("marketplace plugin entry version must be 0.1.0")

    if baseline is not None:
        if set(baseline) != PUBLIC_BASELINE_KEYS:
            errors.append(
                "references/claude-baseline.json: public baseline keys differ: "
                f"actual={sorted(baseline)}, expected={sorted(PUBLIC_BASELINE_KEYS)}"
            )
        private_observations = find_keys(baseline, PRIVATE_OBSERVATION_KEYS)
        if private_observations:
            errors.append(
                "references/claude-baseline.json: private distribution observation keys "
                f"are forbidden: {sorted(private_observations)}"
            )
        if baseline.get("verified_against") != "Claude Code 2.1.222":
            errors.append(
                "references/claude-baseline.json: verified_against must be Claude Code 2.1.222"
            )
        if baseline.get("config_dir_env") != "CLAUDE_CONFIG_DIR":
            errors.append(
                "references/claude-baseline.json: config_dir_env must be CLAUDE_CONFIG_DIR"
            )
        surfaces = set(baseline.get("native_plugin_surfaces", []))
        for surface in (
            "skills",
            "agents",
            "hooks",
            "mcpServers",
            "lspServers",
            "monitors",
            "themes",
            "userConfig",
            "channels",
            "dependencies",
            "defaultEnabled",
        ):
            if surface not in surfaces:
                errors.append(f"references/claude-baseline.json missing native surface: {surface}")

    if errors:
        for error in errors:
            print(f"validate_public_contracts.py: {error}", file=sys.stderr)
        return 1
    print("validate_public_contracts.py: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
