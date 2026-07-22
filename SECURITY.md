# Security Policy

## Supported surface

Security reporting covers the setup catalog, the managed Claude Code
`settings.json` surface, the lifecycle CLI, public contracts, documentation, the
`nddev-builder` marketplace artifacts, and GitHub workflows in this repository.
Only the latest numeric release is supported.

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/NDDev-it-com/nddev-claude-app/security/advisories/new).
Do not publish exploit details, credentials, tokens, private configuration, or
backup contents in an issue or pull request.

Include the affected command or path, reproduction steps, impact, and a
non-sensitive description of the environment. The maintainer aims to
acknowledge a report within 5 business days, triage it within 10 business days,
and provide a fix or mitigation plan for an accepted report within 30 business
days. These targets are best-effort.

## Baseline controls

- The CLI never defaults to `~/.claude`; target operations require an explicit
  absolute `--target`.
- The target, its managed files, backup pool, and catalog reject unsafe
  symlinks and special files. Managed files also reject hard-link aliases.
- The setup lifecycle changes only the managed `settings.json` keys
  (`extraKnownMarketplaces.<marketplace-name>` and
  `enabledPlugins.<plugin>@<marketplace>`) and writes the
  `NDDEV-CLAUDE-SETUP.json` stamp inside the target. Every unmanaged
  `settings.json` key is preserved verbatim.
- The CLI-owned paths `plugins/known_marketplaces.json`, `plugins/marketplaces`,
  `plugins/cache`, and `plugins/data` are preserved, never authored, by this
  module; `.credentials.json`, `projects`, and `~/.claude.json` are never
  touched.
- Existing target directory modes are preserved; newly created targets use mode
  `0700`, and managed files and backup payloads require mode `0600`.
- Existing unmanaged managed-path names and drifted managed files fail closed.
- Backup envelopes and installed stamps are bound to the canonical target; the
  backup pool is the sibling `.<target-name>.nddev-claude-backups` directory
  with ten slots, restorable through `restore --backup <0..9>`.
- Mutations use an exclusive sibling lock, same-parent staging, an atomic
  rename, bounded backup rotation, postcondition checks, and rollback on
  failure.
- Managed and backup files use owner-only permissions.
- `apply` and `switch` register the `nddev-builder` marketplace and enable its
  plugin through the managed `settings.json` keys only. They do not bypass
  normal Claude Code configuration precedence or administrator-managed
  settings, and they are not an administrator enforcement mechanism.
- The builder generator refuses symlinked output paths and implicit overwrite,
  stages complete creation plans through anchored no-follow descriptors, writes
  mode `0600`, and rolls back multi-file failures byte-for-byte. Its checker
  uses bounded fail-closed traversal and reads stable regular files through
  no-follow descriptors. Static checks do not replace Claude Code runtime
  discovery, plugin trust review, MCP authentication, or application security.
- Public workflows use least privilege and immutable action/workflow pins.
- Full behavioral, mutation, platform, and release validation remains in the
  private NDDev harness; no private fixtures or evidence are distributed here.

## Out of scope

- Claude Code runtime vulnerabilities not caused by this module.
- Higher-precedence Claude Code configuration, command line flags, or managed
  settings that intentionally override or restrict the installed defaults.
- Modified forks or manual edits that bypass the lifecycle contract.
- Recovery after an uncatchable interruption where an operator deletes the
  fail-closed lock, recovery hold, or backup pool without inspection.
