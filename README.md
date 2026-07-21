# NDDev Claude Code Setup Manager

`nddev-claude-app` is a dependency-free manager for a caller-selected Claude
Code home (`~/.claude` or an explicit target). It installs a selected NDDev
marketplace of plugins into that target, updates it in place, switches to a
different marketplace, and removes it — all cleanly and reversibly, owning only
the files it manages and leaving credentials, projects, and unrelated user
state untouched.

The repository also publishes the independently installable `nddev-builder`
Claude Code marketplace/plugin.

> Status: **skeleton (0.1.0, unreleased)**. Lifecycle, contract, and builder
> surfaces are being brought up against the current Claude Code plugin format.

## Lifecycle (target-explicit)

```bash
python3 cli-tools/nddev_claude.py list
python3 cli-tools/nddev_claude.py status  --target /absolute/path/to/claude-home
python3 cli-tools/nddev_claude.py plan   --setup <id> --target /absolute/path/to/claude-home
python3 cli-tools/nddev_claude.py apply  --setup <id> --target /absolute/path/to/claude-home
python3 cli-tools/nddev_claude.py switch --setup <id> --target /absolute/path/to/claude-home
python3 cli-tools/nddev_claude.py remove --target /absolute/path/to/claude-home
```

`apply` installs a missing target or updates the current setup. `switch`
changes marketplace identity. Every mutation is atomic with a target-bound
backup and rollback on failure; the manager never infers or defaults to
`~/.claude`.

## Layout

- `cli-tools/nddev_claude.py` — the setup manager.
- `setups/<id>/` — selectable marketplace setups.
- `plugins/nddev-builder/` — the native Claude Code marketplace/plugin.
- `config/nddev-contract.json`, `build/version.json`, `build/manifest.json` —
  public contract and build metadata.
