# SECURITY_MODEL.md

This document describes the security design of RetroIPTVGuide.

---

# 1. Threat Model

Primary concerns:

- malicious playlists
- unauthorized admin access
- external stream abuse
- injection attacks

---

# 2. Authentication

Admin functionality requires login credentials.

Admin-only features include:

- tuner management
- diagnostics tools
- configuration changes
- Admin recovery requires filesystem access
- No in-app password bypass exists (intentional security design)

---

# 3. Input Validation

User-supplied inputs are validated to prevent:

- command injection
- path traversal
- malformed playlist attacks

---

# 4. Network Exposure

Only the web interface port must be exposed.

Default:

5000/tcp

No direct access to system files or shell commands is provided through the web interface.

---

# 5. Dependency Security

Dependencies are managed through requirements.txt.

Security scanning recommendations:

- pip-audit
- GitHub Dependabot
- container vulnerability scans

---

# 6. Future Improvements

Potential improvements:

- role-based permissions
- API authentication
- stricter input sanitization
- container sandboxing
