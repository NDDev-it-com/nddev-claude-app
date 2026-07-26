---
name: claude-plugin-checker
description: Validate a native Claude Code plugin — manifest shape, component discovery, path variables, and the marketplace entry. Use before enabling, bundling, or releasing a plugin.
---

# Claude Plugin Checker

Statically validate a plugin. Confirm it loads only when a real Claude Code CLI
test environment is intentionally available.

## Checks

1. `.claude-plugin/plugin.json` parses; `name` is present, kebab-case, and
   unchanged from prior releases; known fields have correct types; no
   unrecognized required fields.
2. Declared component paths resolve; default dirs (`skills/`, `agents/`,
   `hooks/hooks.json`, `.mcp.json`, `.lsp.json`, `monitors/`, `themes/`) are
   discovered where present.
3. `${CLAUDE_PLUGIN_ROOT}` (not a hard-coded path) is used for bundled scripts.
4. Plugin-shipped agents do not declare unsupported `hooks`, `mcpServers`, or
   `permissionMode` fields.
5. `userConfig`, `channels`, `dependencies`, and `defaultEnabled` match the
   current Claude Code manifest schema when present.
6. No credentials, live tokens, or unfinished filler text in tracked files.
7. Marketplace entry (if any) has a valid `source`, unique `name`, and optional
   metadata that matches the plugin manifest.

## Result

Return PASS for offline audits only when static checks pass. If `claude plugin
validate . --strict` is part of the requested environment, report its result
separately with the exact artifact, field, and reproduction for any failure.
