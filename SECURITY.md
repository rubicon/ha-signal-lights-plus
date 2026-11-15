# Security Policy

## Supported versions

Security fixes are provided for the latest release of Signal Lights Plus only. Please upgrade to the newest release before reporting an issue.

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Report vulnerabilities privately through GitHub's Private Vulnerability Reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue, the affected version, and how to reproduce it.

Expect an acknowledgement within a few business days, updates while the report is investigated, and credit in the release notes when a fix ships unless you ask to stay anonymous.

## Scope

Signal Lights Plus runs inside Home Assistant. Relevant reports include anything that lets an unprivileged Home Assistant user or a network peer run templates they should not, change signals or lights without permission, read data they should not, or crash Home Assistant. Include your Home Assistant version and the integration version.

## Problems in the upstream project

Signal Lights Plus is a fork of [prestomation/ha-signal-lights](https://github.com/prestomation/ha-signal-lights). If a vulnerability is in code that also exists upstream, report it here as well; the fix is offered upstream once it is released here.
