# 02 · Secrets & credentials handling

This path needs two kinds of secret, and they live in two different places.
Getting the *placement* right matters more than anything else here — a
credential in the wrong plane either doesn't work or leaks.

| Secret | What it authenticates | Where it belongs |
|---|---|---|
| **AWS credentials** | Opening the SSM session (`ProxyCommand`) | Customize → Credentials → AWS |
| **SSH private key** | Logging into the head node | Settings → Compute (at provider registration) |

## Golden rules

1. **Never hardcode a secret** in a job script, skill, artifact, or notebook
   cell. Not the AWS keys, not the SSH key.
2. **Never print or echo a credential value.** `host.credentials.get()`
   deliberately redacts values from cell output — pass them straight to a client
   library or write them to the file that consumes them; don't `print()` them.
3. **Minimize standing exposure.** The Claude Science Credentials store can't
   hold temporary AWS credentials in the current version (see §1), so a
   long-lived IAM key is unavoidable there — compensate with tight scope,
   rotation, and a dedicated user.
4. **Scope to the minimum.** The AWS policy should allow `ssm:StartSession` on
   the one instance and nothing else (policy in `01-setup-ssm-ssh.md`).

## 1 · AWS credentials for the SSM ProxyCommand

The `ProxyCommand` runs `aws ssm start-session`, so it needs AWS credentials
**where the platform opens the SSH connection** — not in your `python`/`r` data
kernel, and not on your laptop.

**How to provide them:** Customize → Credentials → Add Credential → AWS. Once
saved, the credential is retrievable in the control plane:

```python
# repl tool — values are redacted from output by design
cred = host.credentials.get("pcluster-aws")     # -> {access_key_id, secret_access_key, region, ...}
```

**What the Credentials store actually accepts (current version):** an AWS
credential here is a **static access-key pair** — `access_key_id` +
`secret_access_key` (+ region). There is **no `session_token` field**, so
**STS / SSO temporary credentials cannot be stored** in Customize → Credentials.
In practice this means a **long-lived IAM user access key** is what you register.
SSO / IAM Identity Center is not a usable option *through the Credentials store*.

Because the key is long-lived, treat it as a standing liability and harden it:

- **Dedicated IAM user** for this integration — never a personal or broadly
  privileged key.
- **Tight policy** — `ssm:StartSession` on the one instance and nothing else
  (policy in `01-setup-ssm-ssh.md`).
- **Rotate on a schedule**, and revoke immediately if the workstation is lost.

See `05-least-privilege-iam.md` for a Terraform plan that provisions exactly such
a user — one whose key can *only* open an SSM session to a single instance — and
an explanation of why that shrinks the static key's blast radius to almost
nothing.

**The one exception — desktop `--profile`.** On a desktop install the
`ProxyCommand` runs on your Mac and reads `~/.aws/credentials` via
`--profile <name>` (see §below), *not* the Credentials store. There, the profile
is governed by your Mac's own AWS config, so an SSO-backed profile
(`aws sso login`) could in principle supply short-lived credentials — **but only
if the process the platform uses to open the connection inherits your refreshed
SSO session**, which is environment-dependent and untested here. Don't assume it
works; if you need SSO, validate it end-to-end with the `env -i` reproduction in
`04-troubleshooting.md` §D.1 before relying on it.

**The `aws` binary and `session-manager-plugin` must be findable where the
ProxyCommand runs — this is a common trap.** On a macOS desktop install the
connection is opened by a GUI process with `launchd`'s minimal `PATH`
(`/usr/bin:/bin`), which does **not** include Homebrew. If `aws` isn't found — or
if `aws` is found but the `session-manager-plugin` it calls *by name* isn't — the
SSM session dies and the probe fails with `Connection closed by UNKNOWN port
65535`. **Prepend `PATH` inside the `ProxyCommand`** so both resolve (an absolute
path to `aws` alone is not enough, because `aws` still looks up the plugin on
`PATH`):

```
ProxyCommand sh -c "PATH=/opt/homebrew/bin:/usr/local/bin:$PATH \
    aws ssm start-session --profile <aws-profile> --target %h \
    --document-name AWS-StartSSHSession --parameters 'portNumber=%p' --region <region>"
```

Find the directory with `which aws session-manager-plugin` in a terminal
(`/opt/homebrew/bin` on Apple Silicon, `/usr/local/bin` on Intel). On a desktop
install `--profile <name>` **is required** because the CLI reads your Mac's
`~/.aws/credentials`; drop it only if creds are injected as env vars where the
connection is opened. Full diagnosis in `04-troubleshooting.md` §D.1.

## 2 · SSH private key for the head node

This is the key in the `IdentityFile` line of your `ssh_config`. Supply it
**at provider registration** (Settings → Compute), where the platform stores it
for the connection. Do **not** paste it into a job script, an artifact, or a
skill.

- Use a **dedicated key** for this host, not a personal all-access key.
- On ParallelCluster the login user is typically `ec2-user` (Amazon Linux) or
  `ubuntu` (Ubuntu 22.04 AMIs) — match `User` in the config.

## Decision summary

Running jobs on the cluster needs just **two** secrets you provide: the AWS
credential (Customize → Credentials) for the SSM tunnel and the SSH key (at
provider registration). Neither should ever appear in a script, artifact, or log.
