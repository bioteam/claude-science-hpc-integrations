##
## AWS provider + account lookup.
##
## In your own infra repo you almost certainly already configure the aws
## provider elsewhere; if so, drop this file and keep only the
## aws_caller_identity data source (or reference your existing one). It is kept
## here so the example is self-contained and `terraform validate` runs clean.
##
provider "aws" {
  region = var.aws_region
}

# Supplies the account id at plan time so the ARNs in the policy document never
# have to hard-code it.
data "aws_caller_identity" "current" {}
