# Changelog

All notable changes to this repository are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Because this is a documentation + Agent-Skills repo (not a released package),
versions track meaningful content milestones rather than an installable artifact.

## [Unreleased]

## [0.1.0] - 2026-07-01

Initial public release: connect Claude Science to private-subnet AWS HPC
(ParallelCluster / PCS) by proxying SSH over AWS Systems Manager (SSM).

### Added
- **Onboarding guide** `Connecting-Claude-Science-to-AWS.md` — end-to-end setup
  for macOS and Windows: device prerequisites, `~/.aws` and `~/.ssh/config`, a
  local SSM-over-SSH test, and the three Claude Science settings (Compute host,
  AWS credential, pinned Scratch root).
- **Skill: `aws-hpc-slurm-ssm-connector`** — submit / monitor / harvest plain
  Slurm jobs over SSM; field-verified end-to-end against a live AWS ParallelCluster.
- **Skill: `schrodinger-aws-hpc-ssm-connector`** — the same SSM→SSH transport plus
  the Schrödinger Suite jobserver layer (`jsc` / `testapp`).
- **`iam-user-for-ssm-sessions/`** — a least-privilege IAM machine identity that
  can only open an SSM SSH/port-forward session to one instance, in two build
  paths: a self-contained Terraform example and a manual AWS-console walkthrough
  with the real JSON policy.
- **Terraform tooling** — repo-root `.tflint.hcl`, `.pre-commit-config.yaml`
  (fmt / tflint / trivy / checkov / gitleaks), and a GitHub Actions workflow, all
  scoped to the deployable `iam-user-for-ssm-sessions/terraform-example`.
- Repo docs: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`,
  `ACKNOWLEDGEMENTS.md` (with thanks to Tenvie Therapeutics for cluster access),
  and architecture diagrams.

[Unreleased]: https://github.com/bioteam/claude-science-hpc-integrations/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bioteam/claude-science-hpc-integrations/releases/tag/v0.1.0
