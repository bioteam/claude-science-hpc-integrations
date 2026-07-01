# Helpers

Reusable reference material that skills and how-tos draw on: snippets, checklists,
config templates, and cheat-sheets. If a piece of content is cited by more than one
skill or how-to, it belongs here.

## What goes here

- **Snippets** — small, self-contained command or code fragments
  (`helpers/snippets/<name>.sh`, `.py`, …).
- **Templates** — starter config files with placeholders
  (`helpers/templates/slurm-batch.sbatch`, `helpers/templates/pcluster-config.yaml`).
- **Checklists** — pre-flight / review lists (`helpers/checklists/<name>.md`).
- **Cheat-sheets** — quick-reference tables (`helpers/cheatsheets/<name>.md`).

## Conventions

- Name files for what they do; keep each one single-purpose.
- Every template uses placeholders (`<CLUSTER>`, `<PARTITION>`, `<ACCOUNT_ID>`) — this
  repo is PUBLIC, so no real account IDs, secrets, internal hostnames, or PII.
- Reference a helper from a skill/how-to by relative path so links survive moves.

## Index

_No helpers published yet — add yours here as `- **path** — one-line summary`._
