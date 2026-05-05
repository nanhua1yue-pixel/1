# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This repository is currently a bare scaffold. As of the latest commit, it contains only:

- `README.md` — a single-line placeholder (`# 1`)
- `.git/` metadata

There is no source code, build system, package manifest, test suite, lint configuration, CI pipeline, or language toolchain established yet. There are no Cursor rules, Copilot instructions, or other agent-facing configuration files.

## Guidance for Future Sessions

Because nothing has been committed to define structure, treat the first substantive change as a greenfield decision:

- Confirm with the user what language, framework, and tooling the project should use before scaffolding files — do not assume.
- Once a stack is chosen, update this file with the real build/test/lint commands and an architecture overview. The instructions above (placeholder status) should be replaced, not appended to.

## Branch Convention

Development for the current task is expected to happen on `claude/add-claude-documentation-sXmrY` (per the session task brief). The default branch is `main`.
