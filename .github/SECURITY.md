# Security Policy

OptiCore is an open-source options pricing library. We take security vulnerabilities seriously.

## Reporting a Vulnerability

If you discover a security vulnerability within OptiCore, please report it responsibly:

**Private vulnerability reporting (preferred):**
Use GitHub's [Private vulnerability reporting](https://github.com/vivek-varma/opticore/security/advisories/new) form to report the issue directly to the maintainers.

**Disclosure Policy:**

- Please allow a reasonable time for a fix before disclosing any vulnerability publicly
- We aim to acknowledge reports within 48 hours and provide an estimated timeline for remediation
- We follow a coordinated disclosure process
- Researchers who report valid vulnerabilities will be credited in the security advisory when appropriate

**Scope:**
- Security vulnerabilities in the C++ numerical core (`src/`, `include/`)
- Security vulnerabilities in the Python API (`python/`)
- Vulnerabilities in third-party dependencies (ib_async, nanobind, etc.)

**Out of Scope:**
- Social engineering attacks
- Physical security issues
- Denial of service attacks on public endpoints (this is a library, not a service)
