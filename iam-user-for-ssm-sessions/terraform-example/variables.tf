##
## Inputs.
##
## These are the caller-supplied values referenced by
## user_claude_science_ssm.tf. Provide them via a terraform.tfvars file (see
## terraform.tfvars.example) or -var flags. None carry a default: the region and
## naming inputs are environment-specific and should be set deliberately.
##
variable "aws_region" {
  description = "AWS region hosting the target instance and the SSM session (e.g. us-east-1)."
  type        = string
}

variable "account_name" {
  description = "Short account label used to name the IAM policy (e.g. platform)."
  type        = string
}

variable "region_short_name" {
  description = "Short region label used to name the IAM policy (e.g. use1)."
  type        = string
}
