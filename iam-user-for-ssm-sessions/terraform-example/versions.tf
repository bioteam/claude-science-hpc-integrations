##
## Provider + version constraints.
##
## Pinned so the example is reproducible and passes tflint's
## terraform_required_version / terraform_required_providers rules. Widen or
## narrow these to match the repo you drop this into.
##
terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.40"
    }
  }
}
