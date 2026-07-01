# Terraform example — least-privilege SSM IAM user

Self-contained Terraform that provisions the `claude-science-ssm-initiator` IAM
user: a machine identity whose only capability is to open an SSM SSH /
port-forward session to **one** EC2 instance, with the static access key stored
in Secrets Manager.

**This is the reference; the full write-up lives one level up.** For the security
model, a line-by-line explanation of every permission, the ⚠️ credential-handling
warning, and how the key lands in / is retrieved from Secrets Manager, read
[`../README.md`](../README.md). No Terraform? Use
[`../manual-example/`](../manual-example/) instead.

## Files

| File | Purpose |
|------|---------|
| `user_claude_science_ssm.tf` | The IAM user, static access key, Secrets Manager storage, and the three-statement least-privilege policy. |
| `variables.tf` | Caller-supplied inputs: `aws_region`, `account_name`, `region_short_name`. |
| `providers.tf` | AWS provider + `aws_caller_identity` lookup. Drop this if your own repo already configures the provider. |
| `versions.tf` | Terraform + AWS provider version constraints. |
| `terraform.tfvars.example` | Copy to `terraform.tfvars` (gitignored) and edit. |

## Quickstart

This is an **example**, not a published module — copy these files into your own
infra repo and adapt them.

```bash
cp terraform.tfvars.example terraform.tfvars   # then edit the values
# Set the target instance id in user_claude_science_ssm.tf
# (local.claude_science_ssm_target_instance_id — currently the placeholder
# i-0123456789abcdef0).
terraform init
terraform plan
terraform apply
```

The access key is written straight into Secrets Manager
(`service_iam/claude-science-ssm-initiator-key`) and is **never** emitted as a
Terraform output. Retrieval and rotation are covered in
[`../README.md`](../README.md#retrieving-the-key-pair).

## Lint & scan

Config lives at the repo root ([`.tflint.hcl`](../../.tflint.hcl),
[`.pre-commit-config.yaml`](../../.pre-commit-config.yaml)). Run the same checks
CI does:

```bash
terraform fmt -check -diff
terraform init -backend=false && terraform validate
tflint --init && tflint --config="$(git rev-parse --show-toplevel)/.tflint.hcl"
trivy config . --severity MEDIUM,HIGH,CRITICAL
checkov -d . --quiet --compact
```

The handful of intentional findings (direct-to-user attachment, mandatory static
key, default KMS key, manual rotation) are documented as inline `#tfsec:ignore` /
`#checkov:skip` suppressions with rationale in `user_claude_science_ssm.tf`.
