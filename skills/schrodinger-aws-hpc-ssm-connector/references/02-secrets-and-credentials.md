# 02 · Secrets & credentials handling

This path needs three different kinds of secret, and they live in three
different places. Getting the *placement* right matters more than anything else
here — a credential in the wrong plane either doesn't work or leaks.

| Secret | What it authenticates | Where it belongs |
|---|---|---|
| **AWS credentials** | Opening the SSM session (`ProxyCommand`) | Customize → Credentials → AWS |
| **SSH private key** | Logging into the head node | Settings → Compute (at provider registration) |
| **Jobserver PKI cert** | Talking to `jobserverd:8030` (gRPC) | Persisted on the cluster's EFS-mounted home (no capture needed) |

## Golden rules (apply to all three)

1. **Never hardcode a secret** in a job script, skill, artifact, or notebook
   cell. Not the AWS keys, not the SSH key, not the cert's private key.
2. **Never print or echo a credential value.** `host.credentials.get()`
   deliberately redacts values from cell output — pass them straight to a client
   library or write them to the file that consumes them; don't `print()` them.
3. **Minimize standing exposure.** The Claude Science Credentials store can't
   hold temporary AWS credentials in the current version (see §1), so a
   long-lived IAM key is unavoidable there — compensate with tight scope,
   rotation, and a dedicated user. Prefer a cert you can re-enroll over one you
   cached.
4. **Scope to the minimum.** The AWS policy should allow `ssm:StartSession` on
   the one instance and nothing else (policy in `01-setup-ssm-ssh.md`).
5. **Keep the private key on the cluster.** Running `jsc`/`testapp` on the
   submit node never moves a jobserver key off the cluster — this is why it's
   the supported posture.

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

> The AWS credential authenticates *opening the tunnel*. It has nothing to do
> with Schrödinger or the jobserver — those come next.

## 2 · SSH private key for the head node

This is the key in the `IdentityFile` line of your `ssh_config`. Supply it
**at provider registration** (Settings → Compute), where the platform stores it
for the connection. Do **not** paste it into a job script, an artifact, or a
skill.

- Use a **dedicated key** for this host, not a personal all-access key.
- On ParallelCluster the login user is typically `ec2-user` (Amazon Linux) or
  `ubuntu` (Ubuntu 22.04 AMIs) — match `User` in the config.

## 3 · Jobserver PKI certificate — the two-phase model

This is the subtle one, and the reason it needs its own treatment.

### How jobserver auth actually works

Authentication to `jobserverd` is **two-phase**:

1. **Enrollment (one-time, SSH-authenticated bootstrap).** You run
   `jsc cert get <host>:8030`. This performs an authenticated handshake (a
   password prompt to the Virtual Cluster, or a socket-auth bootstrap that may
   require the initial SSH trust) and, on success, writes a **per-user
   certificate + private key** into `~/.schrodinger/jobserver.config`. The key
   is a **2048-bit RSA** keypair (OpenSSL 3 rejects the older 1024-bit keys —
   see troubleshooting).
2. **Steady state (pure PKI, no repeat SSH).** Every subsequent `jsc` /
   `testapp` / Maestro call authenticates with that certificate over gRPC/TLS.
   It needs only **network reachability to `:8030`** plus the cert — no further
   SSH login. On the submit node that reachability is already there on the
   cluster network.

The `jobserver.config` file is **version-agnostic**: one enrolled certificate
works across every installed Schrödinger release simultaneously.

### The certificate lives on the cluster — no capture needed

When `jsc`/`testapp` run **on the submit node** (via the native compute
provider), the certificate already lives in the user's EFS-mounted
`~/.schrodinger/jobserver.config` and **persists across sessions**. There is
nothing to capture, store, or restore — this is the simplest and safest posture.

- Keep the cert **2048-bit** (a 1024-bit cert fails on an OpenSSL-3 jobserver —
  rotate first; see troubleshooting).
- **Never write the private key to an artifact, a job script, or stdout.** The
  `jobserver.config` contains a base64-encoded private key — treat the whole file
  as a secret.
- **Do not hand-edit `jobserver.config`.** If it's wrong, re-enroll (`jsc cert
  remove` then `jsc cert get`) rather than editing.

### Service / automation accounts

For non-interactive accounts (automation, workers) an admin can issue a
single-use enrollment password on the jobserver host:

```bash
# On the Job Server host, as root:
sudo -u jobserver bash -l -c "$SCHRODINGER/jsc admin adduser <service-account>"
```

The operator then runs the standard `jsc cert remove` / `jsc cert get` sequence,
supplying that password at the prompt. Capture the resulting config as above.

## Decision summary

Running jobs on the cluster needs just **two** secrets you provide: the AWS
credential (Customize → Credentials) for the SSM tunnel and the SSH key (at
provider registration). The jobserver certificate takes care of itself on the
cluster's EFS-mounted home — nothing to capture or restore.
