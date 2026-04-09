# Security Policy

## Supported Versions

RetroIPTVGuide follows a rolling release model. Security fixes are applied to the current active release series and may not be back-ported to older versions.

Users are strongly encouraged to stay on the latest release.

| Version | Supported |
|--------|-----------|
| 4.x (latest) | ✅ Supported |
| 3.x | ❌ Not supported |
| < 3.0 | ❌ Not supported |

Security fixes are included in the next available patch release whenever possible.

If you are running an older unsupported version, please upgrade to the latest release before reporting a security issue.

---

## Reporting a Vulnerability

If you discover a security vulnerability in **RetroIPTVGuide**, please report it responsibly.

### Preferred Method

Open a **private security advisory** on GitHub:

https://github.com/thehack904/RetroIPTVGuide/security/advisories

This allows the issue to be discussed privately before public disclosure.

### Alternative Method

If GitHub Security Advisories cannot be used, you may open a GitHub Issue labeled **Security (Public)** or contact the maintainer through the repository.

Please include the following information when possible:

- Description of the vulnerability
- Steps to reproduce the issue
- Affected version(s)
- Potential impact
- Any suggested remediation

### Response Expectations

- Initial response: typically within **48–72 hours**
- Investigation and confirmation: varies depending on severity
- Fix timeline: addressed in the **next patch or minor release**

Severity is evaluated based on impact, exploitability, and affected scope.
Critical vulnerabilities will be prioritized for immediate patching.

### Responsible Disclosure

Please **do not publicly disclose security vulnerabilities** until a fix has been released or a mitigation has been provided.

Responsible disclosure helps ensure users can update safely.

### Scope

This policy covers vulnerabilities related to:

- Authentication or authorization bypass
- Remote code execution
- Injection vulnerabilities
- Sensitive data exposure
- Dependency vulnerabilities
- Configuration weaknesses

Issues related to feature requests, installation problems, or general bugs should be reported through the normal GitHub **Issues** page.

## Deployment Responsibility

RetroIPTVGuide is designed for use within trusted or controlled network environments.

Security of the deployment environment is the responsibility of the operator, including:
- Network exposure (port forwarding, reverse proxies, VPN access)
- Firewall configuration
- Host system hardening

Reports related solely to insecure deployment configurations (e.g., exposing the application directly to the public internet without additional protections) are considered out of scope unless a specific software vulnerability is identified.

## Out of Scope

The following are generally not considered security vulnerabilities:

- Issues caused by insecure deployment configurations
- Use of weak or default credentials after initial setup
- Misconfigured reverse proxies, VPNs, or firewalls
- Third-party IPTV content or playlist sources

However, if a software flaw enables exploitation beyond expected behavior, it should still be reported.
