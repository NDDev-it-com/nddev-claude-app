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

> Status: **0.2.0, unreleased**. The public contract targets Claude Code
> `2.1.226` and its native plugin format.

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

## Immutable ai_stp provider path

Provider protocol v3 adds one exact path for both prepared and composed
setups: an immutable `ai-stp-bundle/1` is validated, planned without target
mutation, confirmed by its exact `ai-stp-provider-plan/3` digest, and applied
only after the canonical target is locked and revalidated. The resulting
`NDDEV-CLAUDE-PROVIDER.json` binds the installed native files to the setup
passport, ordered exact component references, logical and byte-level bundle
digests, provider build/release identities, approved plan, ownership manifest,
and target-bound backup.

Protocol-v3 locking uses the canonical target directory inode and keeps its
backup/control data under `.nddev-claude-provider-backups/` inside the exact
writable target. This lets a consumer deny network and expose no writable
parent or sibling paths to the provider. Transaction directories are
same-filesystem, target-local, and removed before the operation returns.

The `stable` and `edge` names in the standalone catalog are acquisition
channels, not immutable setup versions. An ai_stp prepared setup must resolve
all channel content into an exact component graph and bundle before provider
planning. Reusing a setup version with different bytes is therefore rejected
by the bundle and plan digests. The standalone catalog remains available for
target-explicit marketplace management, but its channel ID is never imported
as an ai_stp `SetupVersion` identity.

The capability report is machine-readable:

```bash
python3 cli-tools/nddev_claude.py provider-info
```

Claude Code itself and launch remain host-owned and intentionally unsupported
by this provider. Arbitrary plugin, hook, and setting components also fail
closed until an exact bundle representation can preserve Claude's native
marketplace and settings-merge semantics; supported composed components use
only the declared Claude-native file surfaces.

## Layout

- `cli-tools/nddev_claude.py` — the setup manager.
- `cli-tools/provider_protocol_v3.py` — dependency-free exact bundle/plan
  validation shared by the public provider commands.
- `setups/<id>/` — selectable marketplace setups.
- `plugins/nddev-builder/` — the native Claude Code marketplace/plugin.
- `config/nddev-contract.json`, `build/version.json`, `build/manifest.json` —
  public contract and build metadata.
