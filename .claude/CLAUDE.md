# Claude Code repository contract

> Provisional hand-authored projection (pending GDS onboarding).

## Scope

- Public module `nddev-claude-app`: a Claude Code marketplace/plugin setup
  manager and the native `nddev-builder` marketplace.
- Canonical facts: `.gds/repository.yaml`.

## Boundaries

- One independent mutation boundary; preserve unrelated work.
- Do not copy private validation tooling into this module.

## Safety

- External writes require explicit approval.
- Manager owns only its two `settings.json` keys + stamp; never touch
  `.credentials.json`, `projects/`, `~/.claude.json`, `plugins/` registry.

## Verification

- Test: `python3 cli-tools/validate_public_contracts.py`.

## Done

- Required checks pass or are explicitly reported `NOT_PROVEN`.
- No secret, private-context leak, or unrelated change is introduced.
