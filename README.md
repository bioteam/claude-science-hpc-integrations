# claude-science-hpc-integrations

Skills, how-to guides, and supporting infrastructure examples from
[BioTeam](https://bioteam.net) for connecting the
[**Claude Science Platform**](https://claude.com/product/claude-science) to the
scientific and high-performance computing (HPC) resources it can **invoke and
leverage**.

Everything here has one purpose: let Claude Science reach real compute — Slurm
clusters, AWS ParallelCluster, molecular-simulation jobservers — so it can stage
inputs, submit and monitor jobs, and harvest results as first-class artifacts.
The material is the reusable, field-verified recipes that make that connection
work in practice: job scheduling, cluster provisioning, simulation suites, and
the credentials and operational glue that tie them together.

## How it connects Claude Science to HPC

Claude Science reaches external compute through its **native connectors**. The
relevant one here is the **SSH connector** — Claude Science's compute provider
speaks SSH. But production AWS HPC (ParallelCluster, PCS) usually lives in a
**private subnet inside a workload VPC with no public IP**, so there is no SSH
endpoint to point the connector at, and opening one (public IP, inbound `:22`, a
bastion) is exactly what security-conscious accounts don't want.

The methods in this repo are a deliberate **work-around for the native SSH
connector**: they adapt it to ride over **AWS Systems Manager (SSM)**. An
`aws ssm start-session` `ProxyCommand` in `ssh_config` turns the SSM channel into
an ordinary SSH connection to the private head/login node — no inbound ports, no
public IP, no bastion, just an IAM-scoped SSM session. Claude Science then submits
and monitors Slurm (or Schrödinger jobserver) jobs on the login node exactly as if
it had SSHed in directly, and only result files come back.

![Claude Science connects to a private-subnet AWS ParallelCluster by tunnelling its SSH compute provider over an AWS SSM session](assets/claude-science-ssm-architecture.png)

> **Direction of travel:** this is a work-around for *today's* connectors. We are
> modifying the SSH connector to use AWS SSM natively for securely reaching AWS HPC
> in private subnets / workload VPCs; as that lands, these recipes will track it.
> The [`iam-user-for-ssm-sessions/`](iam-user-for-ssm-sessions/) credential and the
> `ProxyCommand` pattern are the building blocks either way.

**Start here:** [**Connecting Claude Science to AWS**](Connecting-Claude-Science-to-AWS.md)
is the end-to-end setup guide — device prerequisites (macOS + Windows), the
`~/.aws` and `~/.ssh/config` files, how to test SSM-over-SSH locally, and the three
Claude Science → Settings to configure.

## What's here

| Path | Contents |
|-----------|----------|
| [`Connecting-Claude-Science-to-AWS.md`](Connecting-Claude-Science-to-AWS.md) | End-to-end setup guide (macOS + Windows): device prerequisites, `~/.aws` + `~/.ssh/config`, a local SSM-over-SSH test, and the three Claude Science → Settings. |
| [`skills/`](skills/) | Claude [Agent Skills](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills) — each a self-contained folder with a `SKILL.md` (YAML front matter + instructions) that Claude Science loads on demand. Currently: [`aws-hpc-slurm-ssm-connector`](skills/aws-hpc-slurm-ssm-connector) (plain Slurm over SSM) and [`schrodinger-aws-hpc-ssm-connector`](skills/schrodinger-aws-hpc-ssm-connector) (adds the Schrödinger jobserver layer). |
| [`iam-user-for-ssm-sessions/`](iam-user-for-ssm-sessions/) | A least-privilege IAM machine identity that can open an SSM SSH/port-forward session to exactly one EC2 instance — the credential the connector skills register in Claude Science. Ships **two build paths**: a [Terraform example](iam-user-for-ssm-sessions/terraform-example/) and a [manual console walkthrough](iam-user-for-ssm-sessions/manual-example/) with the real JSON policy. |

Start with each directory's own `README.md` for the index and usage details.

Two conventional homes described in [CONTRIBUTING.md](CONTRIBUTING.md) — `howtos/`
(human-readable task guides) and `helpers/` (snippets, checklists, config
templates) — are not yet populated; add them when the first item lands.

## Terraform tooling

Terraform in this repo (currently under `iam-user-for-ssm-sessions/`) is
formatted, linted, and statically security-scanned. Config lives at the repo root:

| File | Purpose |
|------|---------|
| [`.pre-commit-config.yaml`](.pre-commit-config.yaml) | Local hooks: `terraform_fmt`, `tflint`, `trivy`, `checkov`, plus `gitleaks` secret scanning. |
| [`.tflint.hcl`](.tflint.hcl) | TFLint config — core Terraform ruleset + AWS ruleset. |
| [`.github/workflows/terraform.yml`](.github/workflows/terraform.yml) | CI: `fmt → validate → tflint → trivy → checkov` on any `*.tf` change. |

Set it up once, then let it run on every commit that touches Terraform:

```bash
pip install pre-commit    # or: brew install pre-commit
pre-commit install
tflint --init             # installs the AWS ruleset plugin
```

## Scope

In scope:

- Slurm and workload-scheduler operations (submission, accounting, GRES/GPU, troubleshooting)
- AWS HPC: ParallelCluster, PCS, Batch, HealthOmics
- Molecular simulation & structural biology suites (Schrödinger, GROMACS, RELION, CryoSPARC, PLUMED)
- MCP servers and clients for HPC/science (remote execution, documentation RAG, host inventories)
- Container and environment tooling for scientific workloads (Apptainer/Singularity, Spack, modules)

Out of scope: anything containing secrets, customer data, or internal-only
infrastructure identifiers. See [SECURITY](#security--what-not-to-commit) below.

## Using a skill

These are portable Claude Agent Skills — Claude Science, Claude Code, and other
Agent-Skills-aware clients discover them by folder.

- **Claude Science** — point your skill source at this repo (or a skill folder),
  then load it, e.g. `skill({skill: "aws-hpc-slurm-ssm-connector"})`. See each
  skill's own `README.md` for the Claude Science wiring.
- **Claude Code** — copy or symlink the folder into `~/.claude/skills/`:

```bash
git clone https://github.com/bioteam/claude-science-hpc-integrations.git
ln -s "$PWD/claude-science-hpc-integrations/skills/<skill-name>" ~/.claude/skills/<skill-name>
```

Claude reads the `description` in each skill's front matter to decide when to load
it; you do not invoke skills manually.

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

## Acknowledgements

Live testing and validation of these skills ran against a real production-style
AWS HPC environment. See [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md) — with thanks
to [Tenvie Therapeutics](https://tenvie.com/).

## License

[MIT](LICENSE) © BioTeam, Inc.
