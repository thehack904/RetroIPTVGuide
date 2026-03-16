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

If GitHub Security Advisories cannot be used, you may open a GitHub Issue marked **Security** or contact the maintainer through the repository.

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
