# 01 · SSH-over-SSM setup and provider registration

Goal: make the private-subnet ParallelCluster head node look like an ordinary
SSH host, so Claude Science's native compute provider can open a connection to
it and submit Slurm jobs.

> **Two things are user actions, not agent actions.** Adding a compute provider
> (Settings → Compute) and adding credentials (Customize → Credentials) are done
> by you in the UI. The agent drives everything *after* the provider appears in
> `list_compute`.

## Prerequisites (where the connection is opened)

The SSM `ProxyCommand` runs **wherever the platform opens the SSH connection**,
not on your laptop. That host must have:

- **AWS CLI v2** and the **`session-manager-plugin`** installed and on `PATH`.
- **AWS credentials** with permission to start an SSM session to the target
  instance (least-privilege policy below). Provide these via Customize →
  Credentials — see `02-secrets-and-credentials.md`.
- The target EC2 instance must have the **SSM agent running** and an instance
  role allowing SSM (this is the cluster side; already true if you reach it
  with `aws ssm start-session` today).

Confirm your own access works before wiring Claude Science:

```bash
aws ssm start-session --target i-0123456789abcdef0    # should drop you into a shell
```

## The `ssh_config` entry

```sshconfig
# ~/.ssh/config  (on the host where the platform opens SSH connections)

Host pcluster-ssm
    HostName        i-0123456789abcdef0          # the EC2 instance-id of the head node
    User            ec2-user                     # or 'ubuntu' on Ubuntu 22.04 AMIs
    IdentityFile    ~/.ssh/pcluster_key          # head-node login key (see secrets guide)

    # --- Transport: open the SSH connection *through* an SSM session ---
    # PATH prepend is REQUIRED on a macOS desktop app (see note below): it lets
    # the ProxyCommand find BOTH the aws CLI and the session-manager-plugin it
    # calls by name. Use the FULL PATH to the dir holding them — find it with
    # `which aws session-manager-plugin` (usually /opt/homebrew/bin on Apple
    # Silicon, /usr/local/bin on Intel Macs; on Linux typically /usr/bin or
    # /usr/local/bin, where this launchd-PATH workaround is usually unnecessary).
    ProxyCommand    sh -c "PATH=/opt/homebrew/bin:/usr/local/bin:$PATH \
                        /opt/homebrew/bin/aws ssm start-session \
                        --profile <aws-profile> --target %h \
                        --document-name AWS-StartSSHSession \
                        --parameters 'portNumber=%p' --region <region>"

    # Keep the tunnel healthy for long-running harvests
    ServerAliveInterval 30
    ServerAliveCountMax 4
```

Notes:

- `%h` expands to `HostName` (the instance-id) and `%p` to the port — the SSM
  document (`AWS-StartSSHSession`, the one the IAM policy below allow-lists)
  tunnels SSH over the session. If your setup requires `AWS-StartSSHSessionToHost`
  instead, add that document ARN to the policy too — otherwise
  `SessionDocumentAccessCheck` denies it.
- **`PATH` is the #1 gotcha on a macOS desktop install (verified).** The
  `ProxyCommand` runs where the app opens the connection — on a Mac that's a GUI
  process with `launchd`'s minimal PATH, which can't find Homebrew-installed
  `aws` / `session-manager-plugin`. The example above **prepends PATH inside the
  ProxyCommand** and uses the full path to `aws` for exactly this reason — an
  absolute path to `aws` alone is not enough, because `aws` still looks up the
  plugin on `PATH`. Symptom if you skip this: `Connection closed by UNKNOWN port
  65535`, identical with and without `--profile`. Full diagnosis in
  `04-troubleshooting.md` §D.1.
- **`--profile` vs. injected creds depends on where the connection is opened.**
  On a **desktop install** the CLI reads your Mac's `~/.aws/credentials`, so
  `--profile <name>` **is required**. Only drop it if the platform injects AWS
  creds as env vars in the connecting environment. Add `--region <region>` to be
  explicit. See `04-troubleshooting.md` §D.1 for how to tell which case you're
  in.

## Least-privilege AWS policy for SSM

Scope the credentials to *starting a session on the one instance*, nothing more:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StartSSMSessionToHeadNode",
      "Effect": "Allow",
      "Action": "ssm:StartSession",
      "Resource": [
        "arn:aws:ec2:REGION:ACCOUNT:instance/i-0123456789abcdef0",
        "arn:aws:ssm:REGION::document/AWS-StartSSHSession"
      ],
      "Condition": {
        "BoolIfExists": { "ssm:SessionDocumentAccessCheck": "true" }
      }
    },
    {
      "Sid": "OwnSessionChannels",
      "Effect": "Allow",
      "Action": [
        "ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel",
        "ssm:TerminateSession", "ssm:ResumeSession"
      ],
      "Resource": "arn:aws:ssm:*:*:session/${aws:username}-*"
    }
  ]
}
```

Two easy-to-miss details (both explained in `05-least-privilege-iam.md`):
**(1)** AWS-managed session documents are AWS-owned, so their ARN has an **empty
account field** — `arn:aws:ssm:REGION::document/AWS-...`. Pinning your account id
there makes the request never match and `StartSession` is denied. **(2)** The
`ssm:SessionDocumentAccessCheck: true` condition is **required** — without it,
holding `StartSession` implicitly grants the root-capable `RunShell` document and
the document allow-list is bypassed.

> **Prefer the Terraform version — it is the source of truth.** The JSON above is
> a **minimal, SSH-only illustration**. The canonical, maintained policy lives in
> `05-least-privilege-iam.md` + the repo's `iam-user-for-ssm-sessions/`; it
> provisions a dedicated IAM *user*, stores the key in Secrets Manager, pins the
> attachment set, and also allow-lists the two port-forwarding documents for the
> port-forward / jobserver scenario. If the inline JSON and the canonical plan ever
> differ, the canonical plan wins.

Replace `REGION`, `ACCOUNT`, and the instance-id. In the current version of
Claude Science the Credentials store holds **only a static IAM access-key pair**
(no session-token field), so a long-lived IAM user key is what you'll register —
harden it with a tight policy like the one above and regular rotation. See the
secrets guide for details.

## Register the provider (Settings → Compute)

1. Settings → Compute → add an SSH host.
2. Supply the connection details. If the platform lets you reference an
   `ssh_config` `Host` alias, point it at `pcluster-ssm`. If it asks for fields
   directly, provide `HostName` / `User` / key and the **`ProxyCommand`** string
   verbatim (this is the load-bearing field for SSM).
3. **Set `scratch_root`** to a writable shared path (e.g. `/shared/scratch/<user>`)
   — `submit_job` refuses to run without it (see `03-run-and-test.md`).
4. Save. The provider now appears as `ssh:pcluster-ssm` in `list_compute`.

## Smoke test (the only way to confirm the two conditions)

After registration, run **one** reachability check before any real job:

```python
# repl tool
c = host.compute.create("ssh:pcluster-ssm")
print(c.call_command(
    "hostname; id; echo ---; sinfo -s; echo ---; squeue",
    intent="SSM/SSH reachability + Slurm visibility check on pcluster-ssm",
    login_shell=True))
```

**Clean output** — the login node's hostname, your uid, a `sinfo` partition
table, and an (empty) `squeue` header — means the platform honours your
`ssh_config` and has the SSM tooling + credentials. Record the channel as
`verified` in `compute_details`. Verified live output (2026-07-01, Tenvie
cluster) is in `assets/captures/01-reachability-smoke-test.txt`:

```
ip-10-0-0-10
uid=1001(hpcuser) gid=1001(hpc-users) groups=1001(hpc-users)
PARTITION     AVAIL  TIMELIMIT   NODES(A/I/O/T) NODELIST
cpu*             up   infinite        0/20/0/20 cpu-dy-[1-19],cpu-st-1
...
```

**Hangs or `retry_after_user_action: true`** → one of the two conditions isn't
met (config not read, or missing AWS creds/plugin where the platform connects
from). See `04-troubleshooting.md` → "SSM / ssh_config failure modes." Do not
loop retries; fix the condition or fall back.

Once the smoke test is clean, proceed to `03-run-and-test.md` for real jobs.
