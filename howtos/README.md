# How-tos

Task-oriented guides for scientific & HPC workflows. Written for a human to follow by
hand, but also useful as context handed to a Claude agent.

A how-to differs from a skill: a **skill** is machine-loaded and drives Claude's
behavior automatically; a **how-to** is a document you read (or paste in) that explains
a procedure. When a how-to matures into something you want an agent to do repeatably,
promote it to a `skills/` entry.

## Writing a how-to

- One Markdown file per topic: `howtos/<verb>-<subject>.md`
  (e.g. `submit-array-job-slurm.md`, `enable-gpu-accounting-parallelcluster.md`).
  If it carries images or sample files, use a folder: `howtos/<topic>/README.md`.
- Open with a **When to use this** line and the assumed starting state.
- Give concrete, ordered steps with copy-pasteable commands. Flag destructive actions.
- End with a **Verify** section: how the reader confirms it worked.
- PUBLIC repo — placeholders only, no real account IDs, secrets, hostnames, or PII.

## Suggested topics

Slurm submission & accounting · GRES/GPU configuration · ParallelCluster / PCS bring-up
· Batch & HealthOmics pipelines · Schrödinger / GROMACS / RELION / CryoSPARC job setup ·
Apptainer/Singularity on shared clusters · MCP server setup for HPC.

## Index

_No how-tos published yet — add yours here as `- **title** — one-line summary`._
