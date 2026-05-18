<div align="center">

# 🔒 Security Policy

**EPL — English Programming Language**

</div>

---

## Supported Versions

| Version | Status | Support Level |
|---------|--------|---------------|
| `7.x` | ✅ Active | Full security support |
| `< 7.0` | ❌ EOL | No support — upgrade immediately |

Only the current major release line receives active security patches.

---

## Reporting a Vulnerability

> **⚠️ Do NOT publish exploit details in a public issue.**

### Preferred Reporting Channels

| Priority | Method |
|----------|--------|
| **1st** | [GitHub Private Vulnerability Reporting](https://github.com/abneeshsingh21/EPL/security/advisories/new) |
| **2nd** | Email: **singhabneesh250@gmail.com** (subject: `[SECURITY] EPL Vulnerability Report`) |
| **Fallback** | Open a minimal public issue requesting a secure reporting channel — **without disclosing exploit details** |

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact assessment
- Suggested fix (if any)

---

## Response Timeline

| Severity | Acknowledgment | Fix Target |
|----------|----------------|------------|
| 🔴 **Critical** | Within 48 hours | 7 days |
| 🟠 **High** | Within 7 days | 30 days |
| 🟡 **Medium** | Within 14 days | Next scheduled release |
| 🟢 **Low** | Within 30 days | Next scheduled release |

These are targets, not guarantees, but they define the expected maintainer response standard.

---

## High-Sensitivity Areas

The following components are considered security-critical and receive heightened scrutiny:

| Area | Risk | Files |
|------|------|-------|
| **Package Manager** | Supply chain, manifest injection | `epl/package_manager.py` |
| **Python Bridge** | Arbitrary code execution | `epl/interpreter.py` (`Use python`) |
| **JS/TS Bridge** | Subprocess injection, npm supply chain | `epl/js_bridge/` |
| **Web Server** | Request handling, XSS, SSRF | `epl/web.py`, `epl/asgi.py` |
| **File I/O** | Path traversal, arbitrary file access | `epl/stdlib.py` (file operations) |
| **Cloud Operations** | Credential exposure, S3/Lambda abuse | `epl/cloud.py` |
| **Archive Handling** | Zip slip, decompression bombs | `epl/package_manager.py` |
| **Process Execution** | Command injection | `epl/stdlib.py` (`run_command`) |
| **Template Rendering** | Server-side template injection | `epl/web.py` (template engine) |

---

## Security Expectations for Contributors

All security-sensitive changes **must** include:

- ✅ Regression tests covering the vulnerability
- ✅ Clear explanation of impact and attack vector
- ✅ Notes about backward compatibility or required user action
- ✅ Updated `CHANGELOG.md` under the `### Security` heading

---

## Release Expectations for Security Fixes

- Security fixes include regression test coverage
- User-visible risk or operator action is documented in release notes
- Emergency patches may ship outside the normal feature release cadence
- Critical vulnerabilities trigger an immediate point release

---

<div align="center">

**Thank you for helping keep EPL secure.** 🛡️

</div>
