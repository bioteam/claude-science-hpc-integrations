# 05 · Least-privilege IAM user for SSM (Terraform)

`02-secrets-and-credentials.md` establishes the uncomfortable fact: the Claude
Science Credentials store holds only a **static IAM access-key pair** — no
session token, so no SSO / STS temporary credentials. A long-lived key is
therefore unavoidable. This document shows how to make that long-lived key
**safe to store** by shrinking what it can do to almost nothing: open an SSM
session to **one** instance, with **three** AWS-managed session documents, and
nothing else.

The mitigation for "the key never expires" is not expiry — it's **blast radius**.
A key that can only `ssm:StartSession` to a single login node is worth little to
an attacker who steals it and cannot be used to touch any other AWS resource.

## The idea in one sentence

Provision a dedicated IAM **user** (a machine identity, no console, no SSO)
whose *only* permission is to start an SSH / port-forwarding SSM session to the
one ParallelCluster login node — then put **that** user's access key in Claude
Science → Customize → Credentials.

## Why this specific policy is tight

Three design points make the difference between "an SSM policy" and a genuinely
least-privilege one:

1. **`ssm:StartSession` authorizes against two ARNs at once** — the target
   **instance** *and* the session **document**. The policy allows exactly one
   instance ARN and exactly three AWS-managed document ARNs
   (`AWS-StartSSHSession`, `AWS-StartPortForwardingSession`,
   `AWS-StartPortForwardingSessionToRemoteHost`). No other instance, no other
   document.

2. **`ssm:SessionDocumentAccessCheck = true` is mandatory, not optional.**
   Without this condition, merely holding `StartSession` implicitly grants the
   default `SSM-SessionManagerRunShell` document — a **root-capable interactive
   shell** — which would sail straight past the document allow-list. The
   condition forces the allow-list to be honoured. **This is the single most
   important line in the policy.** Omit it and "SSH-only" silently becomes
   "root shell."

3. **Session lifecycle + messaging channels are scoped to the user's own
   sessions** via `session/${aws:username}-*`. The messaging actions
   (`ssmmessages:*Control/DataChannel`) and `TerminateSession`/`ResumeSession`
   can only act on sessions this principal opened — not anyone else's. Note the
   variable is **`aws:username`** (correct for a non-federated IAM user, whose
   session id is `<username>-<random>`), **not** `aws:userid` (which is for
   federated / assumed-role principals).

A final belt-and-braces control: `aws_iam_user_policy_attachments_exclusive`
pins the user's managed policies to *exactly* this one policy, so an out-of-band
console attachment can't quietly widen the grant later.

## What the key can and cannot do

| An attacker with this key **can** | …and **cannot** |
|---|---|
| Start an SSH/port-forward SSM session to the one login node | Touch any other EC2 instance |
| Open/terminate their own SSM sessions | Open a root shell (RunShell document is blocked) |
| — | Read S3, assume roles, call any non-SSM API |
| — | Reach any instance without also having the SSH host key |

Reaching a shell on the login node still requires the **SSH private key** on top
of the SSM session (the `ProxyCommand` opens an SSH connection *through* the
session). The IAM key alone gets an attacker a transport tunnel to one host and
nothing more.

## The Terraform

A sanitized copy of the plan is bundled at
`assets/user_claude_science_ssm.tf`. Replace the placeholder instance id
(`i-0123456789abcdef0`) and the `var.*` inputs (`aws_region`, `account_name`,
`region_short_name`) with your own; `data.aws_caller_identity.current` supplies
the account id at plan time. Key resources:

- `aws_iam_user.claude_science_ssm` — the machine identity, `path = "/service/"`,
  no console login.
- `aws_iam_access_key.claude_science_ssm` — the static key pair. Terraform writes
  it straight into Secrets Manager and **never** emits it as a plan output.
- `aws_secretsmanager_secret_version.claude_science_ssm_key` — stores both halves
  (+ region + target instance id) as one JSON secret, so the operator retrieves
  the full pair from one place.
- `aws_iam_policy_document.claude_science_ssm_start_session` — the three-statement
  least-privilege policy described above.
- `aws_iam_user_policy_attachments_exclusive` — pins the attachment set.

### ARN subtleties worth not re-learning the hard way

- **AWS-managed session documents are AWS-owned**, so their ARN has an **empty
  account-id field**: `arn:aws:ssm:<region>::document/AWS-...`. If you pin *your*
  account id into that ARN it won't match the request and `StartSession` is
  denied. The plan builds these ARNs with the empty account field on purpose.
- **The instance ARN is an EC2 ARN** (`arn:aws:ec2:...:instance/<id>`), not an
  SSM ARN — `StartSession` authorizes against the EC2 instance resource.

## How to use it end-to-end

1. **Apply the plan** (`terraform apply`) in your infra repo. The access key
   lands in Secrets Manager, not in state output or your shell history.
2. **Retrieve the key pair** from Secrets Manager (console or
   `aws secretsmanager get-secret-value`), by whoever administers credentials.
3. **Store it in Claude Science:** Customize → Credentials → Add Credential →
   AWS, pasting the `aws_access_key_id` and `aws_secret_access_key`. This is the
   credential the SSM `ProxyCommand` uses (see `01-setup-ssm-ssh.md`).
4. **Rotate** by tainting `aws_iam_access_key.claude_science_ssm` and re-applying;
   update the stored credential. Because the key does so little, rotation is
   low-stakes — but a schedule is still good hygiene.

## Where this leaves the credential-safety story

- The Credentials store still holds a **long-lived static key** — that
  constraint hasn't changed.
- But the key is now a **single-instance, SSM-session-only** credential. Its
  standing liability is reduced from "an AWS key" to "a tunnel opener for one
  login node," and even that requires the separate SSH private key to become a
  shell.
- This is the recommended posture for the Credentials-store path: don't fight
  the static-key limitation — **neutralise it with a least-privilege user.**

> The desktop `--profile` path (`01`/`02`) is separate: there the Mac's own AWS
> config supplies credentials and could in principle be SSO-backed. The
> least-privilege user here is aimed at the Credentials-store path, where a
> static key is mandatory.
