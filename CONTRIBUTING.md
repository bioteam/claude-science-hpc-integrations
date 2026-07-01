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
  [`skills/README.md`](skills/README.md) and the
  [`skills/_template/`](skills/_template) starter.
- **`howtos/`** — a human-readable, task-oriented guide. One Markdown file (or one
  folder if it has assets). See [`howtos/README.md`](howtos/README.md).
- **`helpers/`** — reference snippets, checklists, config templates that skills and
  how-tos cite. See [`helpers/README.md`](helpers/README.md).

## 3. Style

- Markdown, wrapped at a sensible width, fenced code blocks with a language tag.
- Lead with *when to use this* — the first paragraph of any doc should tell a reader
  (or an agent) whether they're in the right place.
- Prefer concrete, copy-pasteable commands over prose. Mark anything destructive.
- Keep skill `description` fields specific and trigger-oriented; that text is how
  Claude decides to load the skill.

## 4. Commit messages

- Imperative mood, concise subject line (e.g. `Add slurm-gres-gpu howto`).
- Do **not** add AI co-author/attribution trailers.

## 5. Review

Open a PR against `main`. At minimum, a reviewer confirms the no-secrets checklist
and that new skills have a valid `SKILL.md` front matter block.
