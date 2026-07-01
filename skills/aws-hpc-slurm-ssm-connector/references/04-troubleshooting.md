# 04 · Troubleshooting reference

Each entry: **symptom → cause → fix**. Grouped by layer, most impactful first.
The SSM/ProxyCommand section (§D) is where nearly all first-connection failures
land — start there.

---

## A. SSM / `ssh_config` failure modes (the two unverifiable conditions)

**Symptom.** A `call_command` / `submit_job` hangs or returns
`retry_after_user_action: true` — the host is unreachable, which is a
*connection* failure, not a job error.

**Cause & fix — check both conditions from `01-setup-ssm-ssh.md`:**

1. **The platform's SSH layer isn't reading your `ssh_config`.** Then the
   `ProxyCommand` never runs. Confirm the provider registration actually carries
   the `ProxyCommand` string (some programmatic SSH clients ignore
   `~/.ssh/config` unless told to). If it can't be made to read the config, the
   SSM path won't work — fall back to a plain-SSH route the platform *can* reach
   (e.g. a bastion).
2. **Missing SSM tooling or AWS credentials where the platform connects from.**
   The `ProxyCommand` needs AWS CLI + `session-manager-plugin` + valid AWS
   credentials on the connecting host (not your laptop). Verify the credential
   is present (Customize → Credentials) and scoped for `ssm:StartSession` on the
   instance.

### A.1 — `Connection closed by UNKNOWN port 65535` (proxy pipe ran, session died)

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

> **Verified root cause on a macOS desktop install (2026-07): `PATH`.** A
> **strong tell**: the error is *identical with and without* `--profile`. That
> means the `ProxyCommand` fails **before credentials are ever read** — which is
> a PATH/tooling problem, not a credential problem.

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

## B. IAM / permissions (`StartSession` denied)

**Symptom.** `env -i` reproduction (above) prints an
`AccessDeniedException ... not authorized to perform: ssm:StartSession`.

**Causes & fixes:**

- **The instance ARN or document ARN doesn't match the policy.** `StartSession`
  authorizes against **both** the target instance ARN *and* the session-document
  ARN. AWS-managed documents (`AWS-StartSSHSession`, `AWS-StartPortForwarding*`)
  are AWS-owned, so their ARN has an **empty account field**:
  `arn:aws:ssm:<region>::document/AWS-...`. If you pin your account id into that
  ARN, the request never matches and `StartSession` is denied. See
  `05-least-privilege-iam.md`.
- **`ssm:SessionDocumentAccessCheck` missing.** Without the
  `BoolIfExists ssm:SessionDocumentAccessCheck = true` condition, holding
  `StartSession` implicitly grants the root-capable `RunShell` document — some
  orgs' SCPs block that, denying the whole call. Add the condition.
- **Region mismatch.** The credential/policy region must match the instance's
  region. Pass `--region <region>` explicitly in the ProxyCommand.

---

## C. Ports / firewall / connectivity

**Symptom.** SSH connects but jobs won't launch, or `sinfo`/`squeue` error.

**Causes & fixes:**

- **Slurm control daemons must be running.** On the head node,
  `systemctl status slurmctld` (and `slurmd` on compute nodes) should read
  `active (running)`. `sinfo` returning nothing usually means `slurmctld` is
  down or `SLURM_CONF` isn't set in the non-login environment.
- **`scratch_root` must be a shared path** visible to every compute node
  (FSx Lustre / EFS / NFS) — a login-node-local directory will stage inputs the
  compute node can't see. Verified working: `/shared/scratch/<user>`.
- **Dynamic nodes take time to boot.** A job on a `-dy-` partition sits `CF`
  (CONFIGURING) while ParallelCluster launches an instance; this is normal, not
  a failure. Static (`-st-`) nodes run immediately.

---

## D. Diagnosing a failed job

- **`sacct -j <jobid> --format=JobID,State,ExitCode,Elapsed,NodeList,Reason`** —
  the authoritative post-hoc view. `State=FAILED` with a non-zero `ExitCode`
  points at the script; `State=NODE_FAIL`/`TIMEOUT` points at the allocation.
- **`scontrol show job <jobid>`** while it's queued — the `Reason` field
  (`Resources`, `Priority`, `PartitionNodeLimit`) explains a stuck `PD` job.
- **The Slurm output file** (`--output=<name>-%j.out`) captures the script's
  stdout/stderr on the compute node — declare it in `outputs=[...]` to harvest.
- **The harvested job stdout** from `submit_job` — the `compute_done` payload's
  `featured_files` plus `c.attach_job(job_id).result()` for `output_files`.

---

## Quick triage table

| You see | Most likely | Go to |
|---|---|---|
| `retry_after_user_action: true` / hang | ssh_config not read, or missing AWS creds | §A |
| `Connection closed by UNKNOWN port 65535` | PATH (ProxyCommand can't find aws/plugin) | §A.1 |
| `not authorized to perform: ssm:StartSession` | policy ARN / document / region mismatch | §B |
| `sinfo` empty, jobs won't launch | slurmctld down / SLURM_CONF unset | §C |
| Job stuck `PD` / long `CF` | resources or dynamic-node boot | §C |
| Job `FAILED`, need root cause | `sacct` / Slurm output file | §D |
