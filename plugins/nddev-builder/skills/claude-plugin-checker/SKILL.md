---
name: claude-plugin-checker
description: Validate a native Claude Code plugin — manifest shape, component discovery, path variables, and the marketplace entry. Use before enabling, bundling, or releasing a plugin.
---

# Claude Plugin Checker

Statically validate a plugin, then confirm it loads.

## Checks

1. `.claude-plugin/plugin.json` parses; `name` is present, kebab-case, and
   unchanged from prior releases; known fields have correct types; no
   unrecognized required fields.
2. Declared component paths resolve; default dirs (`skills/`, `agents/`,
   `hooks/hooks.json`, `.mcp.json`) are discovered where present.
3. `${CLAUDE_PLUGIN_ROOT}` (not a hard-coded path) is used for bundled scripts.
4. No credentials, live tokens, or placeholders in tracked files.
5. Marketplace entry (if any) has a valid `source` and unique `name`.

## Result

Run `claude plugin validate . --strict` as the authoritative gate. Return PASS
only when the static checks and that validation both succeed; otherwise FAIL
with the exact artifact, field, and reproduction.
