#!/usr/bin/env bash
# Check repo skills against the Agent Skills spec (agentskills/agentskills skills-ref).
# Third-party skills may warn about extra frontmatter fields (version, argument-hint): harmless in Claude Code.
set -u
for d in .claude/skills/*/; do
  printf '%s: ' "$(basename "$d")"
  uvx --from "git+https://github.com/agentskills/agentskills@83021e2#subdirectory=skills-ref" skills-ref validate "$d" 2>&1 | tail -1
done
