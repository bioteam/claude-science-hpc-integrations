# Skills

Claude [Agent Skills](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills)
for scientific & HPC work. Each skill is a folder containing a `SKILL.md`: YAML front
matter (name + description) followed by Markdown instructions Claude loads on demand.

## Anatomy of a skill

```
skills/
  my-skill/
    SKILL.md        # required — front matter + instructions
    scripts/        # optional — helper scripts the skill calls
    references/     # optional — extra docs the skill points Claude to
```

`SKILL.md` front matter (required keys):

```markdown
---
name: my-skill
description: One or two sentences. Say WHAT it does and WHEN to use it, with the
  trigger phrases a user would type. Claude reads only this text to decide whether
  to load the skill, so be specific and concrete.
---

# my-skill — short title

Instructions for Claude go here…
```

Guidance:

- `name` — lowercase, hyphenated, matches the folder name.
- `description` — the single most important field. It is the only part Claude sees
  before loading; make it trigger-rich (e.g. "Use when the user says …").
- Keep the body focused on the procedure. Push long reference tables into
  `references/` and heavy logic into `scripts/`.

Start from [`_template/`](_template) — copy it to `skills/<your-skill>/` and edit.

## Installing a skill

For Claude Code, symlink or copy the folder into `~/.claude/skills/`:

```bash
ln -s "$PWD/skills/<skill-name>" ~/.claude/skills/<skill-name>
```

## Index

_No published skills yet — add yours here as `- **name** — one-line summary` when you
land it. The [`_template`](_template) folder is a starter, not a published skill._
