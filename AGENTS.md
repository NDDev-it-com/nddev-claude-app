# nddev-claude-app — repository contract

> Provisional hand-authored contract. This repository is intended to be
> GDS-onboarded like the sibling modules; once `gds` runs, AGENTS.md and
> `.claude/CLAUDE.md` become generated projections of `.gds/repository.yaml`.

## Scope

- Public module: a dependency-free Claude Code marketplace/plugin setup manager
  plus the native `nddev-builder` marketplace.
- Roles: `module`. Visibility: `public`. Data: `public`.

## Boundaries

- Treat this Git repository as one independent mutation boundary.
- Preserve unrelated branches, worktrees, submodules, and dirty changes.
- Private tests, benchmarks, and validation tooling live in the `nddev-harnesses`
  control plane, never here.

## Safety

- External writes require explicit approval.
- The manager owns only its `extraKnownMarketplaces`/`enabledPlugins` keys and
  its stamp in a target `~/.claude`; it never touches `.credentials.json`,
  `projects/`, `~/.claude.json`, or the CLI-owned `plugins/` registry.
- Do not commit credentials, runtime state, or generated evidence.

## Verification

```bash
python3 cli-tools/validate_public_contracts.py
```

## Done

- Required checks pass or are explicitly reported `NOT_PROVEN`.
- No secret, private-context leak, or unrelated change is introduced.
