# Security Policy

## Supported Versions

Only the current major release line is actively supported for security fixes.

At the time of writing:

- `7.x` - supported

Older lines should be treated as unsupported unless explicitly stated otherwise in release notes.

## Reporting a Vulnerability

Do not publish a working exploit in a public issue.

Preferred path:

- use GitHub private vulnerability reporting or a private maintainer contact channel if available

Fallback path when no private channel is available:

- open a minimal public issue requesting a secure reporting path without disclosing exploit details

## Response Targets

EPL aims to respond on this timeline:

- critical: acknowledge within 48 hours, target a fix or mitigation within 7 days
- high: acknowledge within 7 days, target a fix within 30 days
- medium or low: address in the next scheduled release unless active exploitation changes the priority

These are targets, not guarantees, but they define the expected maintainer response standard for the project.

## Security Expectations

Security-sensitive changes should include:

- regression tests where feasible
- a clear explanation of impact
- notes about compatibility or required operator action

High-sensitivity areas include:

- package installation and manifest handling
- Python bridge / `Use python`
- web server and request handling
- file-system and process execution features
- archive extraction, download, and GitHub/package workflows

## Release Expectations For Security Fixes

- security fixes should include regression coverage where feasible
- user-visible risk or operator action should be documented in release notes
- emergency fixes may ship outside the normal feature cadence
