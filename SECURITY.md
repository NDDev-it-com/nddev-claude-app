# Security Policy

## Supported surface

Security reporting covers the setup catalog, target-owned Codex CLI installer,
lifecycle CLI, upstream desktop-bridge delegation, public contracts,
documentation, the `nddev-builder` marketplace artifacts, and GitHub workflows
in this repository. Only the latest numeric release is supported.

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/NDDev-it-com/nddev-codex-app/security/advisories/new).
Do not publish exploit details, credentials, tokens, private configuration, or
backup contents in an issue or pull request.

Include the affected command or path, reproduction steps, impact, and a
non-sensitive description of the environment. The maintainer aims to
acknowledge a report within 5 business days, triage it within 10 business days,
and provide a fix or mitigation plan for an accepted report within 30 business
days. These targets are best-effort.

## Baseline controls

- The CLI never defaults to `~/.codex`; target operations require an explicit
  absolute `--target`.
- The target, its managed files, backup pool, and catalog reject unsafe
  symlinks and special files. Managed files also reject hard-link aliases.
- The setup lifecycle changes only `config.toml`, `AGENTS.md`, and
  `NDDEV-CODEX-SETUP.json` inside the target. The software and builder
  lifecycles own only their separately documented standalone, profile, and
  plugin-cache paths. Sibling lock, staging, recovery, and backup paths follow
  the separately documented transaction contract.
- Existing target directory modes are preserved; newly created targets use
  mode `0700`, and managed files and backup payloads require mode `0600`.
- `status` reports a target-level `AGENTS.override.md`; setup planning,
  mutation, restore, and launch reject it because it would take precedence over
  the module-managed `AGENTS.md`.
- Existing unmanaged managed-path names and drifted managed files fail closed.
- Backup envelopes and installed stamps are bound to the canonical target.
- Mutations use an exclusive sibling lock, same-parent staging, bounded backup
  rotation, postcondition checks, and rollback on failure.
- Managed and backup files use owner-only permissions.
- `safe` and `full-auto` install user-level Codex defaults. They do not bypass
  normal configuration precedence or administrator-managed requirements, and
  they are not an administrator enforcement mechanism.
- Permission profiles are a beta Codex surface whose configuration syntax is
  compatible from Codex CLI 0.138.0. This build installs, launches, and tests
  exactly 0.144.6.
- `install-cli` and `update-cli` verify the exact pinned official
  `rust-v0.144.6` installer asset before execution. The official installer then
  downloads the pinned checksum manifest and host package and verifies their
  release digests and package checksum from isolated temporary state with a
  fixed release and install root. Abnormal installer exits terminate its whole
  process group before the NDDev target lock is released.
- `launch` requires a clean managed target and the validated target-owned
  standalone CLI. It sets `CODEX_HOME` only for its child, forwards arguments
  without shell interpolation, and preserves the child exit status.
- On macOS, `desktop` delegates only to `codex app` with an optional validated
  workspace. It does not expose arbitrary download/source flags, implement a
  desktop updater, or claim that the GUI inherits the selected `CODEX_HOME`.
- The builder generator refuses symlinked output paths and implicit overwrite,
  stages complete creation plans through anchored no-follow descriptors, writes
  mode `0600`, and rolls back multi-file failures byte-for-byte. Its checker
  uses bounded fail-closed traversal and reads stable regular files through
  no-follow descriptors. Static checks do not replace Codex runtime discovery,
  hook trust review, MCP authentication, or application security.
- Marketplace registration and plugin installation are performed by the
  target-owned Codex CLI. Codex owns the bounded, exact-validated cache; the
  manager enables the builder in the managed `config.toml` base as a co-owned
  addition that preserves the setup base keys verbatim -- so a plain `codex`
  launch loads it by default -- and also writes a separate
  `nddev-builder.config.toml` activation profile for explicit `--profile`
  selection. A failed installation restores the bounded versioned cache tree
  without touching unrelated plugin state. The profile and cache remain outside
  setup backup/restore and persist independently across setup switching or
  removal; a setup apply or switch drops the base-config enable while they
  survive, and `install-builder` restores it.
- Public workflows use least privilege and immutable action/workflow pins.
- Full behavioral, mutation, platform, and release validation remains in the
  private NDDev harness; no private fixtures or evidence are distributed here.

## Out of scope

- Codex runtime vulnerabilities not caused by this module.
- Desktop application vulnerabilities or updater behavior reached through the
  official `codex app` delegation.
- Higher-precedence Codex configuration, command line flags, or managed
  requirements that intentionally override or restrict the installed defaults.
- Modified forks or manual edits that bypass the lifecycle contract.
- Recovery after an uncatchable interruption where an operator deletes the
  fail-closed lock, recovery hold, or backup pool without inspection.
