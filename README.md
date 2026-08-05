# NDDev Claude Code Setup Manager

`nddev-claude-app` is a dependency-free manager for a caller-selected Claude
Code configuration directory, normally the directory a caller would pass as
`CLAUDE_CONFIG_DIR`. It registers a selected NDDev marketplace of plugins in
that target, updates it in place, switches to a different marketplace, and
removes it cleanly. It owns only the managed `settings.json` entries and its
stamp file, leaving credentials, projects, plugin caches, and unrelated user
state untouched.

The repository also publishes the independently installable `nddev-builder`
Claude Code marketplace/plugin.

> Status: **0.1.0, unreleased**. The public contract targets Claude Code
> `2.1.222` and its native plugin format.

## Lifecycle (target-explicit)

```bash
python3 cli-tools/nddev_claude.py list
python3 cli-tools/nddev_claude.py status  --target /absolute/path/to/claude-home
python3 cli-tools/nddev_claude.py plan   --setup <id> --target /absolute/path/to/claude-home
python3 cli-tools/nddev_claude.py apply  --setup <id> --target /absolute/path/to/claude-home
python3 cli-tools/nddev_claude.py switch --setup <id> --target /absolute/path/to/claude-home
python3 cli-tools/nddev_claude.py remove --target /absolute/path/to/claude-home
```

`apply` creates a missing target directory or updates the current setup.
`switch` changes marketplace identity. Every mutation takes an exclusive target
lock, uses a unique transaction directory, creates target-bound backups, and
rolls back bytes, modes, and target existence on failure. `status` and `plan`
are side-effect-free.

The manager never infers or defaults to `~/.claude`, never executes the
`claude` binary, and does not install or update Claude Code itself.

## Layout

- `cli-tools/nddev_claude.py` — the setup manager.
- `setups/<id>/` — selectable marketplace setups.
- `plugins/nddev-builder/` — the native Claude Code marketplace/plugin.
- `config/nddev-contract.json`, `build/version.json`, `build/manifest.json` —
  public contract and build metadata.
