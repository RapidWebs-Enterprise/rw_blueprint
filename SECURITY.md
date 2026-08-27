# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Report vulnerabilities privately to the project maintainers. We will
acknowledge receipt within 48 hours and provide a timeline for remediation.

## Scope

`rw_blueprint` is a documentation and code-generation tool. It does not itself
mutate live infrastructure. However, generated IaC skeletons may be applied to
real systems — treat generated output with the same care as any
infrastructure-as-code artifact.