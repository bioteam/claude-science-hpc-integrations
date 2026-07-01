# Acknowledgements

## Tenvie Therapeutics

We gratefully thank **[Tenvie Therapeutics](https://tenvie.com/)** for providing
access to their AWS environment for the live testing and validation behind this
repository.

Tenvie allowed their **AWS workload VPC**, **HPC clusters**, and **Schrödinger
Suite installations** to be used to build and confirm the skills and documentation
here end-to-end against real infrastructure — including the SSH-over-SSM connector
pattern, the Slurm submit → monitor → harvest loop, and the Schrödinger jobserver
integration. Because of that access, the failure modes, fixes, and verified
captures in these skills reflect what actually happens on a production-style
private-subnet AWS HPC cluster, not a lab approximation.

All infrastructure-specific identifiers (hostnames, IP addresses, usernames, UIDs,
GIDs, instance IDs, and account numbers) drawn from that environment have been
sanitized or replaced with placeholders before publication; see
[`CONTRIBUTING.md`](CONTRIBUTING.md).

Thank you, Tenvie. 🧬
