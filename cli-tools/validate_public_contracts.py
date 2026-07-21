#!/usr/bin/env python3
"""Validate the public NDDev Claude Code module contracts without private inputs.

Checks only tracked public contract files: the public contract, the build
manifest and version, the plugin marketplace + plugin manifests, and their
version parity. Fails closed with a non-zero exit and one error per problem.
Dependency-free; standard library only.
"""

from __future__ import annotations

import json
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


def load_json(relative: str, errors: list[str]) -> dict | None:
    path = ROOT / relative
    if not path.is_file():
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


def main() -> int:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not (ROOT / relative).exists():
            errors.append(f"missing required public file: {relative}")

    contract = load_json("config/nddev-contract.json", errors)
    manifest = load_json("build/manifest.json", errors)
    version = load_json("build/version.json", errors)

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

    if manifest is not None and version is not None:
        if manifest.get("build_version") != version.get("build_version"):
            errors.append("build_version mismatch between manifest.json and version.json")
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

    marketplace = load_json(".claude-plugin/marketplace.json", errors)
    if marketplace is not None:
        if marketplace.get("name") != "nddev-builder":
            errors.append(".claude-plugin/marketplace.json name must be nddev-builder")
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

    if errors:
        for error in errors:
            print(f"validate_public_contracts.py: {error}", file=sys.stderr)
        return 1
    print("validate_public_contracts.py: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
