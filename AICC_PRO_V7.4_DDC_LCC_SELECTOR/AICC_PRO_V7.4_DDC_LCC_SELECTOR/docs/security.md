# Security and production checklist

- Replace demo authentication and password with OIDC/SAML or a hardened JWT provider.
- Terminate TLS at a reverse proxy; restrict CORS and trusted hosts.
- Move secrets to a secret manager and rotate them.
- Use PostgreSQL least-privilege roles, encrypted backups and tested restore.
- Add malware scanning for uploads and a retention schedule for copyrighted pages.
- Do not enable an external model for page images without institutional approval.
- Apply per-user and per-IP rate limits and centralize structured logs.
- Review role permissions before enabling borrower or circulation data.
