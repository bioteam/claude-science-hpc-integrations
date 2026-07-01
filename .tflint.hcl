##
## TFLint configuration for this repo's Terraform examples.
##
## Runs the core Terraform ruleset (formatting, naming, unused declarations,
## required_version / required_providers) plus the AWS ruleset for
## provider-specific checks. Install plugins with `tflint --init`.
##
config {
  call_module_type = "local"
  force            = false
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "aws" {
  enabled = true
  version = "0.44.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}
