# Changelog

All notable changes to `nddev-claude-app` are documented here.

## [0.1.1] - 2026-07-30

- Included the repository instruction closure in both source and runtime
  release archives so the extracted public validator remains self-contained.

## [0.1.0] - 2026-07-24

- Initial skeleton: Claude Code marketplace/plugin setup manager, native
  `nddev-builder` marketplace, and public contract surfaces.
- Hardened the setup manager against symlink, dangling symlink, hardlink,
  ownership, permission, lock collision, backup collision, and rollback edge
  cases while preserving explicit `CLAUDE_CONFIG_DIR` target behavior.
- Bound the public contract to Claude Code 2.1.220 and its native plugin
  marketplace/settings surfaces.
