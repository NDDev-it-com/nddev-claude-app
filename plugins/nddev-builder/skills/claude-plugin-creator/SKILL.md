---
name: claude-plugin-creator
description: Create a native Claude Code plugin — `.claude-plugin/plugin.json` plus the component directories it declares. Use when scaffolding a new plugin or adding a component family to one.
---

# Claude Plugin Creator

Create the smallest valid plugin that owns the requested behavior.

## Steps

1. Choose a stable kebab-case `name` (the install/enable identity — never change
   it later; use `displayName` for a UI label).
2. Write `.claude-plugin/plugin.json` with `name` (required) and only the
   metadata you can fill honestly (`version`, `description`, `author`, `license`).
   Omit `version` to let the git SHA version it, or set + bump it every release.
3. Add components at the plugin **root** (not inside `.claude-plugin/`):
   `skills/<name>/SKILL.md`, `commands/*.md`, `agents/*.md`,
   `hooks/hooks.json`, `.mcp.json`, `.lsp.json`, `monitors/`, or `themes/`.
   Reference bundled paths with `${CLAUDE_PLUGIN_ROOT}`.
4. Add manifest fields only when they are real: `skills`, `commands`, `agents`,
   `hooks`, `mcpServers`, `lspServers`, `userConfig`, `channels`,
   `dependencies`, and `defaultEnabled`.
5. Validate offline with the checker, then run `claude plugin validate . --strict`
   only in an intentional Claude Code test environment.

## Rules

- Do not put unrecognized keys or wrong-typed known keys in `plugin.json`.
- Do not add `hooks`, `mcpServers`, or `permissionMode` to plugin-shipped
  agents; those agent fields are not supported by Claude Code.
- Do not embed credentials, tokens, or unfinished filler text.
- Prefer `skills/` over legacy `commands/`.
