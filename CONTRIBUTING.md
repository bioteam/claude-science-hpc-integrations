# Contributing

Thanks for adding to the BioTeam Claude science/HPC knowledge base. This repo is
**public**, so the first rule governs everything else.

## 1. Never commit secrets or private data

Before every commit, confirm your change contains **none** of:

- AWS account IDs, ARNs, access/secret keys, session tokens
- Okta app/client IDs, OAuth client secrets, SSM parameter paths
- Internal-only hostnames, private URLs, VPC/subnet/IP details
- Customer names, engagement details, or any PII

Replace real values with placeholders: `<ACCOUNT_ID>`, `<CLUSTER_NAME>`,
`example.internal`, `s3://<BUCKET>/…`. When unsure, leave it out or ask in review.

A quick self-check before pushing:

```bash
git diff --cached | grep -nEi '[0-9]{12}|aws_secret|okta|client_secret|password|BEGIN [A-Z ]*PRIVATE KEY' && echo "REVIEW THESE MATCHES"
```

(Matches are not automatically bad — account IDs vs. a docs example — but every hit
must be looked at by a human before the commit lands.)

## 2. Where things go

- **`skills/`** — a reusable Claude Agent Skill. One folder per skill; see
  [`skills/README.md`](skills/README.md). Start by copying an existing skill folder
  and replacing its `SKILL.md` and contents.
- **`iam-user-for-ssm-sessions/`** (and future infrastructure examples) — Terraform
  and/or console recipes for the AWS resources a skill depends on. See its
  [`README.md`](iam-user-for-ssm-sessions/README.md) for the layout to mirror
  (self-contained example, a README, and — for Terraform — linter-clean code).
- **`howtos/`** — a human-readable, task-oriented guide. Not created yet; when the
  first guide lands, add the folder with its own `README.md` index.
- **`helpers/`** — reference snippets, checklists, config templates that skills and
  how-tos cite. Not created yet; add the folder with a `README.md` when needed.

## 3. Terraform & infrastructure examples

Terraform in this repo is formatted, linted, and statically security-scanned, and
CI enforces it on every `*.tf` change ([`.github/workflows/terraform.yml`](.github/workflows/terraform.yml)).
Before committing Terraform:

```bash
pre-commit install   # once — wires the git hook
tflint --init        # once — installs the AWS ruleset plugin
pre-commit run --all-files   # fmt + tflint + trivy + checkov + gitleaks
```

- Keep examples **self-contained and `terraform validate`-clean** (declare the
  variables and providers they reference), so the scanners have something to check.
- Keep the scan **green**. If a finding is a deliberate design choice, suppress it
  inline with a one-line rationale (`#tfsec:ignore:<id>` / `#checkov:skip=<id>:<why>`)
  rather than leaving it unexplained — see `iam-user-for-ssm-sessions/terraform-example/`
  for the pattern.
- Use placeholders for every real identifier (instance ids, account ids, hostnames),
  exactly as in rule 1.

## 4. Style

- Markdown, wrapped at a sensible width, fenced code blocks with a language tag.
- Lead with *when to use this* — the first paragraph of any doc should tell a reader
  (or an agent) whether they're in the right place.
- Prefer concrete, copy-pasteable commands over prose. Mark anything destructive.
- Keep skill `description` fields specific and trigger-oriented; that text is how
  Claude decides to load the skill.

## 5. Commit messages

- Imperative mood, concise subject line (e.g. `Add slurm-gres-gpu howto`).
- Do **not** add AI co-author/attribution trailers.

## 6. Review

Open a PR against `main`. At minimum, a reviewer confirms the no-secrets checklist,
that new skills have a valid `SKILL.md` front matter block, and that any Terraform
change passes fmt / tflint / trivy / checkov (the CI check must be green).
