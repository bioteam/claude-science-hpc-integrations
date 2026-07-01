# 04 · Troubleshooting reference

Each entry: **symptom → cause → fix**. Grouped by layer, most impactful first.
Sources are the Schrödinger docs, Schrödinger KB (article IDs given), and a
field-captured BioTeam verification note for this platform.

> **First step for any failed job:** collect a postmortem —
> `$SCHRODINGER/jsc postmortem <jobserver-jobid>` bundles the launch,
> jobserver, supervisor, output, and license-server logs into one redacted zip.
> It's the fastest way to get everything below in one place. See "Collecting a
> postmortem" in `03-run-and-test.md` (note: redaction is on by default, and the
> zip lands in the cwd — don't `cd` in the submit script).

---

## A. Weak-RSA client certificate / OpenSSL 3 (the big one)

**Symptom.** After a jobserver upgrade to 2026-1 (or any jobserver ≥ version
73060), you get a **partial failure**: Slurm submission and MMLIBS license
accounting still work, but client-side job tracking — `testapp`, `jsc info`,
Maestro monitoring — hangs or fails with a gRPC TLS handshake error:

```
client certificate uses weak RSA key of 1024 bits.
OpenSSL 3.x requires RSA keys >= 2048 bits.
```

with **gRPC connection error code 14 (`UNAVAILABLE`)**.

**Cause.** Certificates issued before Schrödinger's default key size moved to
2048-bit are 1024-bit, stored in `~/.schrodinger/jobserver.config`. Jobserver
version 73060 is the OpenSSL-3 boundary; OpenSSL 3's security policy rejects the
weak keys at authentication. The job still *runs* (Slurm side is fine) but the
client can't track it (gRPC side rejects the cert).

**Fix (per user).** Re-enroll to generate a fresh 2048-bit keypair:

```bash
jsc cert remove <jobserver_host>:8030      # non-destructive; deletes only the local entry
jsc cert get    <jobserver_host>:8030      # re-registers, generates a 2048-bit keypair
```

- `jsc cert remove` only removes the local config entry; `jsc cert get`
  re-registers and generates a new keypair that passes the ≥2048-bit check.
- The `jobserver.config` is **version-agnostic** — one rotation fixes all
  installed Schrödinger releases at once.
- **Do not hand-edit `jobserver.config`.**

**Audit script** (find affected users by decoding the stored private keys):

```bash
python3 <<'PY'
import json, base64, subprocess, glob
for cfg in glob.glob("/shared/home/*/.schrodinger/jobserver.config"):
    user = cfg.split("/")[3]
    try:
        data = json.load(open(cfg))
    except Exception as e:
        print(f"{user}: read error ({e})"); continue
    for e in data:
        host = e.get("hostname", "?"); port = e.get("jobport", "?")
        priv = e.get("auth", {}).get("private", "")
        if not priv:
            print(f"{user:24s} {host}:{port}  no-private-key"); continue
        pem = base64.b64decode(priv)
        r = subprocess.run(["openssl","rsa","-in","/dev/stdin","-noout","-text"],
                           input=pem, capture_output=True)
        size = "?"
        for ln in (r.stdout + r.stderr).decode().splitlines():
            if "bit" in ln and ("Private-Key" in ln or "Public-Key" in ln):
                size = ln.strip(); break
        print(f"{user:24s} {host}:{port}  {size}")
PY
```

Output showing "1024 bit" flags a broken cert needing rotation.

**Service / automation accounts** (no interactive auth): an admin issues a
single-use password on the jobserver host —
`sudo -u jobserver bash -l -c "$SCHRODINGER/jsc admin adduser <name>"` — then the
operator runs the `jsc cert remove` / `jsc cert get` pair, supplying it at the
prompt.

**Deeper case — server CA itself is 1024-bit.** If client-side rotation *still*
produces a 1024-bit cert (audit re-run unchanged), the server's signing CA is a
1024-bit v1 CA and the fix must happen server-side: a sysadmin stops
`jobserverd`, removes the `server_authentication*` / `supervisor_authentication*`
/ `user_certificate` files in the jobserver config dir, regenerates with
`jsc admin setup-server`, and restarts (Schrödinger KB 629509). Client rotation
is a no-op until that's done.

---

## B. Version-match failures

**Symptom 1 — `No job server was found for -HOST <host>`** (client on release
2025-3+):

```
server <host>:8030: Failed to get job SCHRODINGER ... To use the
IGNORE_SCHRODINGER_HOSTS feature, please run 'jsc job-schrodinger-map' to set up
a runtime path for the launch installation ...
```

**Cause.** With `IGNORE_SCHRODINGER_HOSTS` enabled, the jobserver needs a mapping
from the client's launch installation to a path it recognizes. **Fix:** run
`jsc job-schrodinger-map` to register the launch installation path, or have an
admin add it to `jobserver.installation_parent_directories` in `jobserver.yml`;
or disable the feature if unused (Schrödinger KB 305180).

**Symptom 2 — old client, new jobserver.** Jobs launched from Suite 2023-3 and
below to a jobserver on 2025-4+ fail with
`Failure reason: The job_supervisord process has failed: exit status 2`.
**Cause.** The 2025-4 jobserver's filestore is incompatible with the older
client's file-storage method (Schrödinger KB 529877). **Fix:** the client must
run a compatible (newer) release.

**General rule.** For remote submission the **client must have the same
Schrödinger release installed** as one of the releases on the cluster ("Virtual
Cluster"). Running `jsc`/`testapp` on the submit node avoids this entirely — the
client *is* the submit node, so it already matches a cluster release.

---

## C. Ports / firewall / connectivity

**Symptom.** `jsc hosts list` returns nothing, the connection to `:8030` is
refused, or remote jobs won't launch at all.

**Causes & fixes:**

- **Job Control needs ports > 1024 open** on the remote (Linux) host. If a
  firewall is in place, open the range above 1024.
- **Jobserver gRPC is port 8030.** From the submit node this must be reachable
  on the cluster network — verify with `$SCHRODINGER/jsc server-info
  <jobserver-host>:8030` (should return the server version). If the jobserver is
  a separate host, confirm the submit node can open a TCP socket to it on 8030.
- **Manager/head node must have a stable, resolvable hostname** that always maps
  to the same physical host, and compute nodes + submit hosts must be able to
  open sockets to it and to the SLM (Schrödinger License Manager) license server
  (default port 53000; the legacy FlexNet/FlexLM server used 27008 and 53000).
- Confirm the jobserver is running on the head node:
  `systemctl status jobserverd` (also `slurmctld`, `slurmd`) should read
  `active (running)`.

---

## D. SSM / `ssh_config` failure modes (the two unverifiable conditions)

**Symptom.** A `call_command` / `submit_job` hangs or returns
`retry_after_user_action: true` — the host is unreachable, which is a
*connection* failure, not a job error.

**Cause & fix — check both conditions from `01-setup-ssm-ssh.md`:**

1. **The platform's SSH layer isn't reading your `ssh_config`.** Then the
   `ProxyCommand` never runs. Confirm the provider registration
   actually carries the `ProxyCommand` string (some programmatic SSH clients
   ignore `~/.ssh/config` unless told to). If it can't be made to read the
   config, the SSM path won't work — fall back to a plain-SSH route the platform
   *can* reach (e.g. a bastion), or keep an `hpc-remote`-style MCP connector for
   exec.
2. **Missing SSM tooling or AWS credentials where the platform connects from.**
   The `ProxyCommand` needs AWS CLI + `session-manager-plugin` + valid AWS
   credentials on the connecting host (not your laptop). Verify the credential
   is present (Customize → Credentials) and scoped for `ssm:StartSession` on the
   instance.

### D.1 — `Connection closed by UNKNOWN port 65535` (proxy pipe ran, session died)

**Symptom.** Provider probe / `call_command` fails with:

```
probe failed (exit 255): Connection closed by UNKNOWN port 65535
```

**Reading the signature.** The `UNKNOWN` peer at port `65535` is how SSH
describes a connection made over a **`ProxyCommand` pipe** (there is no real
socket peer). So this error *confirms* the platform read your `ssh_config` and
launched the SSM `ProxyCommand` (condition 1 is satisfied) — but the
`ProxyCommand` process exited before the SSH handshake completed. The fault is
in what that process needs: its `PATH`, its AWS tooling, or its credentials.

> **Verified root cause on a macOS desktop install (2026-07): `PATH`.** This was
> the actual failure in the field. A **strong tell**: the error is *identical
> with and without* `--profile`. That means the `ProxyCommand` fails **before
> credentials are ever read** — which is a PATH/tooling problem, not a
> credential problem.

**Most likely cause — `PATH` (macOS desktop app).** The `ProxyCommand` runs
`aws ssm start-session`, and `aws` in turn shells out to
**`session-manager-plugin`** by name. Your **Terminal** finds both because your
shell `PATH` includes Homebrew (`/opt/homebrew/bin` on Apple Silicon,
`/usr/local/bin` on Intel). But a **GUI app** on macOS inherits `launchd`'s
minimal PATH (`/usr/bin:/bin:/usr/sbin:/sbin`), which does **not** include those
— so `aws` (or the plugin it calls) isn't found, the ProxyCommand exits, and ssh
reports exactly this error. An absolute path to `aws` alone is **not enough** —
`aws` still calls the plugin by name, so PATH must be set.

**Fix (verified): prepend PATH inside the `ProxyCommand`.**

```
ProxyCommand sh -c "PATH=/opt/homebrew/bin:/usr/local/bin:$PATH \
    aws ssm start-session --profile <profile> --target %h \
    --document-name AWS-StartSSHSession --parameters 'portNumber=%p' --region <region>"
```

Find your paths with `which aws session-manager-plugin` in a terminal and use
that directory. This single change fixed the connection in the field.

**Isolate the real hidden error.** ssh swallows the ProxyCommand's stderr. To
see it, reproduce the app's stripped environment in a terminal:

```bash
env -i /bin/sh -c '/full/path/to/aws ssm start-session --profile <profile> \
    --target <instance-id> --document-name AWS-StartSSHSession \
    --parameters portNumber=22 --region <region>'
```

Whatever this prints (plugin not found, SSO/credential error, region error) is
the actual fault to fix.

**On credentials — desktop vs. injected.** *Where* the ProxyCommand runs decides
where creds come from:

- **macOS desktop install (verified here):** the ProxyCommand runs on your Mac
  using your Mac's `aws` CLI, which reads `~/.aws/credentials` /
  `~/.aws/config`. Here `--profile <name>` **is required** and must name a
  profile that exists on the Mac. (This is the opposite of what a first pass
  might assume — do **not** drop `--profile` on a desktop install.)
- If instead the connection is opened in an environment where Claude Science
  injects credentials as env vars (`AWS_ACCESS_KEY_ID`, …), then a `--profile`
  reference would point at a missing profile — drop it and let the env vars
  apply. Confirm which case you're in with the `env -i` test above.

**Other causes of the same signature** (rule out after PATH + creds): expired /
rotated credentials; wrong region for the instance; the target instance's IAM
role missing `AmazonSSMManagedInstanceCore`; the SSM agent not running on the
instance; or `HostName` not being the real instance-id. Also confirm the
`--document-name` (`AWS-StartSSHSession`) is one the IAM policy allow-lists — if
your cluster needs `AWS-StartSSHSessionToHost` instead, add it to the policy's
document list too, or `SessionDocumentAccessCheck` denies the session.

**Do not loop retries** on a `retry_after_user_action` — it's deterministic
until the underlying condition changes. Fix the condition, then re-run the
smoke test.

---

## E. Diagnosing a failed job

- **Per-job log** on the submit node:
  `~/.schrodinger/job_server/logs/queue-submission-<job-id>.log`.
- **`jsc info <job-id>`** for status; **`scontrol show job <slurm-id>`** for the
  Slurm view (check `Licenses=` and `Comment=SchrodingerJobId=`).
- **Postmortem archive** for Support: Job Server uses the flow in Schrödinger KB
  912061 (the older Job Control flow is KB 1473).
- **License checking caveats:** the license sensor polls at intervals, so a job
  can occasionally start before a competing checkout registers; suite/PACKAGE
  licenses aren't always fully accounted. Rarely the cause of a hard failure,
  but worth knowing when MMLIBS counts look off.

---

## Quick triage table

| You see | Most likely | Go to |
|---|---|---|
| Job runs in Slurm but `jsc info`/`testapp` hangs (gRPC err 14) | 1024-bit cert on OpenSSL-3 jobserver | §A |
| `No job server was found for -HOST` | IGNORE_SCHRODINGER_HOSTS path mapping | §B |
| `job_supervisord ... exit status 2` | old client → new jobserver | §B |
| `jsc hosts list` empty over forward | port 8030 not forwarded / conn down | §C |
| `retry_after_user_action: true` | ssh_config not read, or missing AWS creds | §D |
| Job failed, need root cause | pull per-job log / postmortem | §E |
