---
name: nddev-builder-orientation
description: Orient in the NDDev Claude Code builder — what each creator/checker skill produces and the native artifact families (plugin, marketplace, skill, command, subagent, hook, MCP). Use first when building or auditing a Claude Code plugin.
---

# NDDev Builder orientation

This marketplace authors and validates **native Claude Code artifacts** against
the current format (`code.claude.com/docs`). Each family ships a conservative
**creator** and a deterministic **checker**.

## Native artifact families

- **Plugin** — `.claude-plugin/plugin.json` (only `name` required) + component
  dirs at plugin root: `skills/`, `commands/`, `agents/`, `hooks/hooks.json`,
  `.mcp.json`, `.lsp.json`.
- **Marketplace** — repo-root `.claude-plugin/marketplace.json` (`name`,
  `owner`, `plugins[]`).
- **Skill** — `skills/<name>/SKILL.md`; only `description` recommended; body
  loads on invoke (progressive disclosure).
- **Command** — a skill as a flat `commands/*.md`; namespaced `/<plugin>:<name>`.
- **Subagent** — `agents/*.md`; `name` + `description` required.
- **Hook** — `hooks/hooks.json`; events + matcher + handlers; `${CLAUDE_PLUGIN_ROOT}`.
- **MCP** — `.mcp.json`; stdio/http/sse/ws; scoped tool names.

## Rules

- Prefer `skills/` over `commands/` for new work.
- `name` is stable identity (`enabledPlugins`/install key); use `displayName`
  for UI, `renames` for migrations.
- Gate every artifact on `claude plugin validate . --strict`.
