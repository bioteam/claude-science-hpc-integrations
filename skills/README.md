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

Start by copying an existing skill folder (e.g.
[`aws-hpc-slurm-ssm-connector/`](aws-hpc-slurm-ssm-connector)) to
`skills/<your-skill>/`, then replace its `SKILL.md` and contents.

## Installing a skill

For Claude Code, symlink or copy the folder into `~/.claude/skills/`:

```bash
ln -s "$PWD/skills/<skill-name>" ~/.claude/skills/<skill-name>
```

## Index

- **[`schrodinger-aws-hpc-ssm-connector`](schrodinger-aws-hpc-ssm-connector)** —
  connect Claude Science to a Schrödinger Suite jobserver on an AWS ParallelCluster
  (or any Slurm HPC) whose head node is reachable only through AWS SSM, then submit,
  monitor, harvest, and postmortem jobs. Field-verified end-to-end.
- **[`aws-hpc-slurm-ssm-connector`](aws-hpc-slurm-ssm-connector)** — connect Claude Science
  to a private-subnet AWS ParallelCluster (or any Slurm HPC) whose head node is
  reachable only through AWS SSM, then submit, monitor, and harvest plain Slurm
  jobs. The transport-only sibling of the Schrödinger connector (no jobserver
  layer). Field-verified end-to-end.

Add new skills here as `- **name** — one-line summary` when you land them.
