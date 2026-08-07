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
  `.mcp.json`, `.lsp.json`, `monitors/`, and `themes/`.
- **Marketplace** — repo-root `.claude-plugin/marketplace.json` (`name`,
  `owner`, `plugins[]`); plugin sources include relative, git-backed, npm, and
  Claude Code 2.1.224+ HTTPS `archive` objects with optional `sha256`.
- **Skill** — `skills/<name>/SKILL.md`; only `description` recommended; body
  loads on invoke (progressive disclosure).
- **Command** — a skill as a flat `commands/*.md`; namespaced `/<plugin>:<name>`.
- **Subagent** — `agents/*.md`; `name` + `description` required.
- **Hook** — `hooks/hooks.json`; events + matcher + handlers; `${CLAUDE_PLUGIN_ROOT}`.
- **MCP** — `.mcp.json`; plugin-scoped stdio/http/sse/ws servers and tools.
- **LSP** — `.lsp.json`; language server command, extensions, and optional
  restart/diagnostic settings.
- **Monitor/theme/config** — experimental monitors and themes plus manifest
  `userConfig`, `channels`, `dependencies`, and `defaultEnabled` where needed.

## Rules

- Prefer `skills/` over `commands/` for new work.
- `name` is stable identity (`enabledPlugins`/install key); use `displayName`
  for UI, `renames` for migrations.
- Gate every artifact on `claude plugin validate . --strict` when a real Claude
  Code CLI is intentionally available; static checks are the offline gate.
- Treat marketplace distribution and organization-managed sync as distinct:
  the latter does not accept npm or archive plugin sources.
