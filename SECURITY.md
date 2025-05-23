# Security Policy

## Supported Versions
Flux supports security updates for the latest minor release:

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | ✅                 |
| < 0.2.0 | ❌                 |

## Reporting a Vulnerability
If you discover a security vulnerability, please report it by emailing [security@flux-community.example.com](mailto:security@flux-community.example.com). Do not disclose the issue publicly until it has been addressed.

### Process
- You will receive a confirmation within 48 hours.
- We will investigate and provide a fix within 14 days for critical issues.
- Once resolved, we will release a security advisory and credit you (if desired).

## Security Best Practices
- Use environment variables for sensitive configurations (e.g., `FLUX_SECURITY_ENCRYPTION_KEY` in `flux.toml`).
- Regularly update dependencies using `poetry update`.
