# claude-science-hpc-integrations

Central store for [BioTeam](https://bioteam.net) Claude skills, how-to guides, and
helper material for scientific & high-performance computing (HPC) integrations.

This repository collects the reusable knowledge that makes Claude (and Claude-based
agents) effective on real HPC and life-science computing work — job scheduling,
cluster provisioning, molecular-simulation suites, MCP servers, and the operational
recipes that tie them together.

## What's here

| Directory   | Contents |
|-------------|----------|
| `skills/`   | Claude [Agent Skills](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills) — each a self-contained folder with a `SKILL.md` (YAML front matter + instructions) that Claude loads on demand. |
| `howtos/`   | Task-oriented guides for humans: step-by-step procedures for HPC/science workflows, written to be followed by hand or handed to an agent as context. |
| `helpers/`  | Reference material, snippets, checklists, and configuration templates that skills and how-tos draw on. |

Start with each directory's own `README.md` for the index and contribution rules.

## Scope

In scope:

- Slurm and workload-scheduler operations (submission, accounting, GRES/GPU, troubleshooting)
- AWS HPC: ParallelCluster, PCS, Batch, HealthOmics
- Molecular simulation & structural biology suites (Schrödinger, GROMACS, RELION, CryoSPARC, PLUMED)
- MCP servers and clients for HPC/science (remote execution, documentation RAG, host inventories)
- Container and environment tooling for scientific workloads (Apptainer/Singularity, Spack, modules)

Out of scope: anything containing secrets, customer data, or internal-only
infrastructure identifiers. See [SECURITY](#security--what-not-to-commit) below.

## Using a skill with Claude

Claude Code and other Agent-Skills-aware clients discover skills by folder. To use a
skill from this repo, copy (or symlink) its folder into your skills directory — for
Claude Code that is `~/.claude/skills/`:

```bash
git clone https://github.com/bioteam/claude-science-hpc-integrations.git
ln -s "$PWD/claude-science-hpc-integrations/skills/<skill-name>" ~/.claude/skills/<skill-name>
```

Claude reads the `description` in each skill's front matter to decide when to load it;
you do not invoke skills manually.

## Security — what NOT to commit

This is a **public** repository. Before committing, confirm your change contains none
of the following:

- AWS account IDs, ARNs, access keys, or secret material of any kind
- Okta app/client IDs, OAuth secrets, SSM parameter names, or other auth identifiers
- Internal-only hostnames, private URLs, or IP addresses
- Customer, engagement, or personally identifiable information (PII)

Use placeholders (`<ACCOUNT_ID>`, `example.internal`, `us-east-1`) instead. When in
doubt, leave it out. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full checklist.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Every skill needs a `SKILL.md`; every how-to
and helper needs a clear title and a one-line summary of when to use it.

## License

[MIT](LICENSE) © BioTeam, Inc.
