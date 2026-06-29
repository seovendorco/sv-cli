# Security Policy

## Reporting vulnerabilities

Please do not open public issues for security vulnerabilities. Report suspected vulnerabilities privately to the maintainers or the security contact designated by SV.

Include:

- Affected version or commit
- Reproduction steps
- Impact
- Any suggested fix

## API-key safety

- Never commit API keys.
- Do not paste real keys into issues, logs, screenshots, examples, or tests.
- Prefer `SV_API_KEY` in CI.
- Local config is stored under `~/.sv/config.json` and should not be copied into repositories.
- Debug output masks common secret fields, including `k`, `api_key`, and tokens.

## Supported versions

During the public beta, security fixes target the latest released version.
