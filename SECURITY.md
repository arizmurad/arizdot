# Security policy

## Supported version

Security fixes target the latest published preview or release. Older previews may require an upgrade. No response-time guarantee is offered.

## Report a vulnerability

Use **Security → Report a vulnerability** on the official GitHub repository when private vulnerability reporting is enabled. Do not post credentials, transcripts, private paths, or working exploit details in a public issue. If the private reporting option is unavailable, open an issue asking for a private reporting channel without disclosing vulnerability details.

The maintainer will review the report and coordinate a fix when possible. Never upload somebody else's conversations or machine configuration to demonstrate a problem.

## Local behavior

arizdot reads local status sources and stores private state under `config/`. It does not call model APIs or upload transcripts. Installation downloads Python dependencies and registers local assistant integrations. Review the scripts before running them. Host tool permissions remain under the user's control.
