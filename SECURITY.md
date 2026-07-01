# Security Policy

## What this repository is (and isn't)

This is a **documentation and Agent-Skills** repository. It ships no running
service and no deployable application — it contains guides, Claude Science skills,
and **example** Terraform / IAM policy you copy into your own AWS account and
adapt. The security surface is therefore mostly about the *guidance* being sound
and about not leaking secrets into a public repo.

## Reporting a vulnerability

If you find a security issue in this repo — a leaked secret or real
infrastructure identifier, a mistake in the least-privilege IAM guidance that
would over-grant access, or anything else that could put a reader's environment
at risk — please report it via an Issue or emailing **dag@bioteam.net**.


## Using the examples safely

The examples here deliberately follow a least-privilege model (an IAM user that
can only open an SSM session to one instance; see
[`iam-user-for-ssm-sessions/`](iam-user-for-ssm-sessions/)). When you adapt them:

- Replace every placeholder (`i-0123456789abcdef0`, `<ACCOUNT_ID>`, `us-east-1`,
  `example.internal`) with your own values.
- Scope the IAM policy to exactly the instance and session documents you need,
  and keep `ssm:SessionDocumentAccessCheck = true` — dropping it silently grants a
  root-capable shell document.
- Treat the static IAM access key as a real credential: store it in Secrets
  Manager / your credential manager, never in a file or chat, and rotate it. See
  the ⚠️ warning in
  [`iam-user-for-ssm-sessions/README.md`](iam-user-for-ssm-sessions/README.md#️-warning--least-privilege-is-not-no-privilege).

## Contributing without leaking secrets

This is a **public** repository. Before every commit, confirm your change
contains no AWS account IDs, access keys, real hostnames/IPs, or other secret
material — use placeholders instead. The full checklist and the `gitleaks`
pre-commit hook are described in [`CONTRIBUTING.md`](CONTRIBUTING.md).
