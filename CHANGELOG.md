# Changelog

All notable changes to `nddev-claude-app` are documented here.

## [0.1.0] - 2026-07-24

- Initial skeleton: Claude Code marketplace/plugin setup manager, native
  `nddev-builder` marketplace, and public contract surfaces.
- Hardened the setup manager against symlink, dangling symlink, hardlink,
  ownership, permission, lock collision, backup collision, and rollback edge
  cases while preserving explicit `CLAUDE_CONFIG_DIR` target behavior.
- Verified the public contract against Claude Code 2.1.220, the current native
  plugin marketplace/settings surfaces, and official release manifest metadata.
