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
   `skills/<name>/SKILL.md`, `agents/*.md`, `hooks/hooks.json`, `.mcp.json`.
   Reference bundled paths with `${CLAUDE_PLUGIN_ROOT}`.
4. Validate: `claude plugin validate . --strict`.

## Rules

- Do not put unrecognized keys or wrong-typed known keys in `plugin.json`.
- Do not embed credentials, tokens, or `[TODO]` placeholders.
- Prefer `skills/` over legacy `commands/`.
