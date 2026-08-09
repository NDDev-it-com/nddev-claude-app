# Changelog

All notable changes to `nddev-claude-app` are documented here.

## [0.2.0] - 2026-08-09

- Add the capability-negotiated provider protocol v3 core without assigning
  Claude host-software or launch ownership to the setup manager.
- Make prepared and composed setups converge on one deterministic
  `ai-stp-bundle/1` validate/plan/apply/status path with exact plan binding,
  post-lock target revalidation, fail-closed native-surface validation, and
  component-level provenance.
- Add a versioned provider state and independent target-bound backup pool with
  exact restore references, pre-restore recovery backups, rollback, drift
  reporting, no-op replacement, and managed residue removal.
- Keep protocol-v3 locks, transactions, and backups inside the exact writable
  target boundary; lock the canonical target inode without widening sandbox
  access to its parent or siblings.
- Classify standalone `stable` and `edge` as acquisition channels rather than
  immutable ai_stp setup versions; ai_stp resolves exact content before the
  bundle reaches the provider.

## [0.1.6] - 2026-08-08

- Revalidate the native marketplace, plugin, hook, skill, agent, settings, and
  archive-source contracts against stable Claude Code 2.1.226.
- Preserve the target-explicit, non-credential-owning setup boundary across
  the 2.1.225 headless-auth and workspace-trust fixes and the 2.1.226
  reliability release; no native plugin-format change was observed.
- Bind the public status banner and `VERSION` file to the canonical build
  version so future runtime promotions cannot leave stale release metadata.

## [0.1.5] - 2026-08-08

- Represent native plugin source kinds as explicit typed records so the
  `url` source kind cannot be confused with a captured runtime URL fact.
- Validate the complete Claude Code 2.1.224 source-kind set and record shape.

## [0.1.4] - 2026-08-08

- Revalidate the native marketplace, plugin, hook, skill, agent, settings, and
  archive-source contracts against stable Claude Code 2.1.224.
- Preserve isolated target ownership while advancing to the upstream release
  with SHA-pinned archive plugin sources, sandbox credential masking, and the
  trailing-slash permission-deny security fix.

## [0.1.3] - 2026-08-06

- Revalidate the native marketplace, plugin, hook, skill, agent, and settings
  contracts against stable Claude Code 2.1.223.
- Retain explicit isolated targets while advancing to the upstream release
  containing permission-prompt, workflow-sandbox, and bypass-policy fixes.

## [0.1.2] - 2026-08-05

- Revalidate the native marketplace, plugin, hook, skill, agent, and settings
  contracts against stable Claude Code 2.1.222.
- Preserve target-explicit setup behavior; Claude Code itself remains a host
  runtime and is never installed into live user state by this manager.

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
